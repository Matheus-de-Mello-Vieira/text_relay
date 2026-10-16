export function initializeImageUpload(setStatus) {
  const imageInput = document.querySelector("#image");
  const submitButton = document.querySelector("#submit");
  const submitLabel = document.querySelector("#submit-label");
  const fileName = document.querySelector("#file-name");
  const filePicker = document.querySelector("#file-picker");
  const clearFileButton = document.querySelector("#clear-file");
  const cropDialog = document.querySelector("#crop-dialog");
  const cropperContainer = document.querySelector("#cropper-container");
  const confirmCropButton = document.querySelector("#confirm-crop");
  const cancelCropButton = document.querySelector("#cancel-crop");
  const rotateLeftButton = document.querySelector("#rotate-left");
  const rotateRightButton = document.querySelector("#rotate-right");
  const resetRotationButton = document.querySelector("#reset-rotation");
  const rotationAngle = document.querySelector("#rotation-angle");
  let cropper = null;
  let cropObjectUrl = null;
  let cropSourceFile = null;
  let focusBeforeCrop = null;
  let rotationDegrees = 0;

  function formatFileSize(bytes) {
    return bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  function updateSelectedFile() {
    const file = imageInput.files[0];
    const hasFile = Boolean(file);
    fileName.querySelector("span").replaceChildren();
    if (file) {
      const name = document.createElement("strong");
      name.textContent = file.name;
      fileName.querySelector("span").append(name, document.createTextNode(` · ${formatFileSize(file.size)}`));
    }
    fileName.classList.toggle("visible", hasFile);
    filePicker.classList.toggle("selected", hasFile);
    submitButton.disabled = !hasFile;
    submitLabel.textContent = hasFile ? "Extract text" : "Choose an image to extract text";
  }
  function setInputFile(file) {
    const files = new DataTransfer();
    if (file) files.items.add(file);
    imageInput.files = files.files;
  }
  function closeCropDialog({ discard = false } = {}) {
    cropper?.destroy();
    cropper = null;
    cropperContainer.replaceChildren();
    cropDialog.hidden = true;
    document.body.classList.remove("crop-open");
    if (focusBeforeCrop?.isConnected) focusBeforeCrop.focus();
    focusBeforeCrop = null;
    if (cropObjectUrl) URL.revokeObjectURL(cropObjectUrl);
    cropObjectUrl = null;
    cropSourceFile = null;
    rotationDegrees = 0;
    rotationAngle.value = "0°";
    rotateLeftButton.disabled = true;
    rotateRightButton.disabled = true;
    resetRotationButton.disabled = true;
    if (discard) {
      setInputFile();
      updateSelectedFile();
      imageInput.focus();
    }
  }
  function rotateImage(degrees) {
    const cropperImage = cropper?.getCropperImage();
    if (!cropperImage) return;
    cropperImage.$rotate(`${degrees}deg`);
    rotationDegrees += degrees;
    rotationAngle.value = `${rotationDegrees}°`;
    resetRotationButton.disabled = rotationDegrees === 0;
  }
  function canvasToBlob(canvas, type) {
    return new Promise((resolve, reject) => canvas.toBlob(
      (blob) => blob ? resolve(blob) : reject(new Error("Could not create the cropped image.")),
      type,
      type === "image/png" ? undefined : 0.95,
    ));
  }
  function openCropDialog(file) {
    const Cropper = window.Cropper?.default;
    if (typeof Cropper !== "function") {
      setInputFile();
      updateSelectedFile();
      setStatus("The image cropper could not be loaded. Try again when the network is available.", "error");
      return;
    }
    closeCropDialog();
    focusBeforeCrop = document.activeElement;
    cropSourceFile = file;
    cropObjectUrl = URL.createObjectURL(file);
    const image = new Image();
    image.alt = "Selected image, ready to crop";
    image.addEventListener("load", () => {
      if (cropDialog.hidden || cropSourceFile !== file) return;
      cropper = new Cropper(image, { container: cropperContainer });
      const cropperImage = cropper.getCropperImage();
      cropperImage.rotatable = true;
      cropperImage.$ready(() => {
        if (cropperImage !== cropper?.getCropperImage()) return;
        cropperImage.$center("contain");
        const imageBounds = cropperImage.getBoundingClientRect();
        const canvasBounds = cropper.getCropperCanvas().getBoundingClientRect();
        const inset = Math.min(10, imageBounds.width / 4, imageBounds.height / 4);
        cropper.getCropperSelection().$change(
          imageBounds.left - canvasBounds.left + inset,
          imageBounds.top - canvasBounds.top + inset,
          imageBounds.width - inset * 2,
          imageBounds.height - inset * 2,
        );
        rotateLeftButton.disabled = false;
        rotateRightButton.disabled = false;
        confirmCropButton.focus();
      });
    }, { once: true });
    image.addEventListener("error", () => {
      if (cropDialog.hidden || cropSourceFile !== file) return;
      closeCropDialog({ discard: true });
      setStatus("Could not read that image. Choose a different image.", "error");
    }, { once: true });
    cropDialog.hidden = false;
    document.body.classList.add("crop-open");
    cancelCropButton.focus();
    image.src = cropObjectUrl;
  }
  async function confirmCrop() {
    const selection = cropper?.getCropperSelection();
    const cropperImage = cropper?.getCropperImage();
    if (!selection || !cropperImage || !cropSourceFile) {
      setStatus("Could not prepare the crop. Choose the image again.", "error");
      closeCropDialog({ discard: true });
      return;
    }
    confirmCropButton.disabled = true;
    cancelCropButton.disabled = true;
    try {
      const displayedWidth = cropperImage.getBoundingClientRect().width;
      const sourceWidth = cropper.element.naturalWidth;
      const outputWidth = displayedWidth && sourceWidth
        ? Math.max(1, Math.round(selection.width * sourceWidth / displayedWidth))
        : undefined;
      const canvas = await selection.$toCanvas(outputWidth ? { width: outputWidth } : undefined);
      const type = cropSourceFile.type;
      const blob = await canvasToBlob(canvas, type);
      const baseName = cropSourceFile.name.replace(/\.[^.]+$/, "") || "image";
      const extension = type === "image/png" ? "png" : type === "image/webp" ? "webp" : "jpg";
      setInputFile(new File([blob], `${baseName}-cropped.${extension}`, { type, lastModified: Date.now() }));
      closeCropDialog();
      updateSelectedFile();
      setStatus("Crop ready to extract text.", "success");
    } catch (error) {
      setStatus(error.message || "Could not create the cropped image.", "error");
    } finally {
      confirmCropButton.disabled = false;
      cancelCropButton.disabled = false;
    }
  }
  function selectImage(file) {
    const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
    if (!allowedTypes.includes(file.type)) {
      setInputFile();
      updateSelectedFile();
      setStatus("Choose a JPG, PNG, or WebP image.", "error");
      return;
    }
    openCropDialog(file);
  }
  imageInput.addEventListener("change", () => {
    const file = imageInput.files[0];
    if (file) selectImage(file);
  });
  clearFileButton.addEventListener("click", () => {
    imageInput.value = "";
    updateSelectedFile();
    imageInput.focus();
  });
  cancelCropButton.addEventListener("click", () => closeCropDialog({ discard: true }));
  rotateLeftButton.addEventListener("click", () => rotateImage(-1));
  rotateRightButton.addEventListener("click", () => rotateImage(1));
  resetRotationButton.addEventListener("click", () => rotateImage(-rotationDegrees));
  cropDialog.querySelector(".crop-dialog-backdrop").addEventListener("click", () => closeCropDialog({ discard: true }));
  cropDialog.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeCropDialog({ discard: true });
    } else if (event.key === "Tab") {
      const focusable = Array.from(cropDialog.querySelectorAll("button:not(:disabled), [tabindex]:not([tabindex='-1'])"))
        .filter((element) => element.getClientRects().length);
      const first = focusable[0];
      const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });
  confirmCropButton.addEventListener("click", confirmCrop);
  ["dragenter", "dragover"].forEach((eventName) => filePicker.addEventListener(eventName, (event) => {
    event.preventDefault();
    filePicker.classList.add("dragging");
  }));
  ["dragleave", "drop"].forEach((eventName) => filePicker.addEventListener(eventName, (event) => {
    event.preventDefault();
    filePicker.classList.remove("dragging");
  }));
  filePicker.addEventListener("drop", (event) => {
    const [file] = event.dataTransfer.files;
    if (!file) return;
    const files = new DataTransfer();
    files.items.add(file);
    imageInput.files = files.files;
    selectImage(file);
  });

  return { imageInput, submitButton, updateSelectedFile };
}
