document.addEventListener("DOMContentLoaded", function () {
	const eventForm = document.getElementById("eventForm");
	const ticketsJsonInput = document.getElementById("ticketsJson");

	const uploadInput = document.getElementById("eventImageInput");
	const uploadPreview = document.getElementById("eventImagePreview");
	const uploadText = document.getElementById("uploadBoxText");
	const uploadBox = uploadPreview ? uploadPreview.closest(".upload-box") : null;
	const openImageEditorBtn = document.getElementById("openImageEditorBtn");
	const imageEditorModal = document.getElementById("imageEditorModal");
	const closeImageEditorBtn = document.getElementById("closeImageEditorBtn");
	const cancelImageEditBtn = document.getElementById("cancelImageEditBtn");
	const confirmImageEditBtn = document.getElementById("confirmImageEditBtn");
	const imageEditorStage = document.getElementById("eventImageStage");
	const imageEditorCanvas = document.getElementById("eventImageCanvas");
	const cropFrame = document.getElementById("cropFrame");
	const imageZoomRangeInput = document.getElementById("imageZoomRange");
	const imageZoomValue = document.getElementById("imageZoomValue");
	const zoomOutBtn = document.getElementById("zoomOutBtn");
	const zoomInBtn = document.getElementById("zoomInBtn");
	const rotateLeftBtn = document.getElementById("rotateLeftBtn");
	const rotateRightBtn = document.getElementById("rotateRightBtn");
	const resetImageTransformBtn = document.getElementById("resetImageTransformBtn");
	const descriptionHiddenInput = document.getElementById("eventDescription");
	const descriptionEditorEl = document.getElementById("eventDescriptionEditor");
	const eventTitleInput = document.getElementById("eventTitle");
	const eventLocationInput = document.getElementById("eventLocation");
	const eventTypeSelect = document.getElementById("eventTypeId");
	const eventStartTimeInput = document.getElementById("startTime");
	const eventEndTimeInput = document.getElementById("endTime");

	let descriptionEditor = null;
	if (descriptionEditorEl && typeof window.Quill !== "undefined") {
		descriptionEditor = new window.Quill("#eventDescriptionEditor", {
			theme: "snow",
			placeholder: "Mo ta su kien...",
			modules: {
				toolbar: "#eventDescriptionToolbar",
			},
		});
	}

	const limitModeInputs = document.querySelectorAll('input[name="limitMode"]');
	const limitQtyBox = document.getElementById("limitQtyBox");
	const limitQuantityInput = document.getElementById("limitQuantity");
	const qtyMinusBtn = document.getElementById("qtyMinus");
	const qtyPlusBtn = document.getElementById("qtyPlus");

	const openTicketFormBtn = document.getElementById("openTicketFormBtn");
	const ticketTypeForm = document.getElementById("ticketTypeForm");
	const cancelTicketBtn = document.getElementById("cancelTicketBtn");
	const ticketTypeList = document.getElementById("ticketTypeList");
	const ticketTypeEmpty = document.getElementById("ticketTypeEmpty");

	const ticketNameInput = document.getElementById("ticketName");
	const ticketPriceInput = document.getElementById("ticketPrice");
	const suggestTicketPriceBtn = document.getElementById("suggestTicketPriceBtn");
	const ticketFreeInput = document.getElementById("ticketFree");
	const ticketQuantityInput = document.getElementById("ticketQuantity");
	const ticketSaleStartInput = document.getElementById("ticketSaleStart");
	const ticketSaleEndInput = document.getElementById("ticketSaleEnd");
	const ticketDescInput = document.getElementById("ticketDesc");
	const floatingEventActions = document.getElementById("floatingEventActions");
	const ticketFormTitle = ticketTypeForm ? ticketTypeForm.querySelector("h2") : null;
	const ticketFormSubmitBtn = ticketTypeForm ? ticketTypeForm.querySelector('button[type="submit"]') : null;
	const flashWrap = document.querySelector(".org-flash-wrap");
	const flashAlerts = flashWrap ? Array.from(flashWrap.querySelectorAll(".alert")) : [];

	const ticketTypes = [];
	const targetImageWidth = 606;
	const targetImageHeight = 241;
	const imageEditorContext = imageEditorCanvas ? imageEditorCanvas.getContext("2d") : null;
	const imageMinZoom = 0.3;
	const imageMaxZoom = 4;
	const imageZoomStep = 0.1;
	const minCropWidth = 80;
	const minCropHeight = 60;

	if (imageEditorCanvas) {
		imageEditorCanvas.width = targetImageWidth;
		imageEditorCanvas.height = targetImageHeight;
	}

	const imageTransform = {
		zoom: 1,
		rotation: 0,
	};

	let sourceEventImageFile = null;
	let sourceEventImageName = "";
	let sourceEventImageMimeType = "image/jpeg";
	let committedImagePreviewDataUrl = "";
	let draftEventImage = null;
	let draftEventImageName = "";
	let draftEventImageMimeType = "image/jpeg";
	let isSavingImageEdit = false;
	let cropBox = null;
	let cropInteraction = null;
	let editingTicketIndex = -1;

	function normalizeImageMimeType(mimeType) {
		if (mimeType === "image/png" || mimeType === "image/webp") {
			return mimeType;
		}
		return "image/jpeg";
	}

	function buildEditedImageName(mimeType) {
		const baseName = (draftEventImageName || sourceEventImageName || "event-image").replace(/\.[^/.]+$/, "");
		const extension = mimeType === "image/png" ? "png" : (mimeType === "image/webp" ? "webp" : "jpg");
		return baseName + "-edited." + extension;
	}

	function updateOpenImageEditorButtonState() {
		if (openImageEditorBtn) {
			openImageEditorBtn.disabled = !sourceEventImageFile;
		}
	}

	function clamp(value, min, max) {
		return Math.max(min, Math.min(max, value));
	}

	function getEditorStageRect() {
		if (!imageEditorStage) {
			return null;
		}

		const rect = imageEditorStage.getBoundingClientRect();
		if (!rect.width || !rect.height) {
			return null;
		}
		return rect;
	}

	function setCropFrameVisible(isVisible) {
		if (!cropFrame) {
			return;
		}
		cropFrame.classList.toggle("is-hidden", !isVisible);
	}

	function updateCropFrameStyle() {
		if (!cropFrame || !cropBox) {
			return;
		}

		cropFrame.style.left = cropBox.x + "px";
		cropFrame.style.top = cropBox.y + "px";
		cropFrame.style.width = cropBox.width + "px";
		cropFrame.style.height = cropBox.height + "px";
	}

	function resetCropFrame() {
		const rect = getEditorStageRect();
		if (!rect) {
			cropBox = null;
			setCropFrameVisible(false);
			return;
		}

		const insetX = rect.width * 0.08;
		const insetY = rect.height * 0.08;
		cropBox = {
			x: insetX,
			y: insetY,
			width: rect.width - insetX * 2,
			height: rect.height - insetY * 2,
		};

		setCropFrameVisible(true);
		updateCropFrameStyle();
	}

	function getCropRectInCanvasCoords() {
		if (!cropBox || !cropFrame || cropFrame.classList.contains("is-hidden") || !imageEditorCanvas) {
			return {
				x: 0,
				y: 0,
				width: imageEditorCanvas ? imageEditorCanvas.width : targetImageWidth,
				height: imageEditorCanvas ? imageEditorCanvas.height : targetImageHeight,
			};
		}

		const rect = getEditorStageRect();
		if (!rect) {
			return {
				x: 0,
				y: 0,
				width: imageEditorCanvas.width,
				height: imageEditorCanvas.height,
			};
		}

		const scaleX = imageEditorCanvas.width / rect.width;
		const scaleY = imageEditorCanvas.height / rect.height;

		const x = clamp(Math.round(cropBox.x * scaleX), 0, imageEditorCanvas.width - 1);
		const y = clamp(Math.round(cropBox.y * scaleY), 0, imageEditorCanvas.height - 1);
		const width = clamp(Math.round(cropBox.width * scaleX), 1, imageEditorCanvas.width - x);
		const height = clamp(Math.round(cropBox.height * scaleY), 1, imageEditorCanvas.height - y);

		return { x: x, y: y, width: width, height: height };
	}

	function openImageEditorModalDialog() {
		if (!imageEditorModal) {
			return;
		}
		imageEditorModal.classList.remove("is-hidden");
		document.body.classList.add("is-modal-open");
	}

	function closeImageEditorModalDialog() {
		if (!imageEditorModal) {
			return;
		}
		imageEditorModal.classList.add("is-hidden");
		document.body.classList.remove("is-modal-open");
	}

	function clearUploadPreview() {
		uploadPreview.classList.add("is-hidden");
		uploadPreview.removeAttribute("src");
		uploadText.style.display = (uploadText.textContent || "").trim() ? "inline" : "none";
		if (uploadBox) {
			uploadBox.classList.remove("has-preview");
		}
	}

	function setUploadPreviewFromDataUrl(dataUrl) {
		if (!dataUrl) {
			clearUploadPreview();
			return;
		}

		uploadPreview.src = dataUrl;
		uploadPreview.classList.remove("is-hidden");
		uploadText.style.display = "none";
		if (uploadBox) {
			uploadBox.classList.add("has-preview");
		}
	}

	function setUploadPreviewFromFile(file) {
		if (!file) {
			clearUploadPreview();
			return;
		}

		const reader = new FileReader();
		reader.onload = function (e) {
			uploadPreview.src = e.target.result;
			uploadPreview.classList.remove("is-hidden");
			uploadText.style.display = "none";
			if (uploadBox) {
				uploadBox.classList.add("has-preview");
			}
		};
		reader.readAsDataURL(file);
	}

	function setImageToolDisabledState(isDisabled) {
		[
			imageZoomRangeInput,
			zoomOutBtn,
			zoomInBtn,
			rotateLeftBtn,
			rotateRightBtn,
			resetImageTransformBtn,
			confirmImageEditBtn,
		].forEach(function (control) {
			if (control) {
				control.disabled = isDisabled;
			}
		});
	}

	function updateImageZoomLabel() {
		if (imageZoomValue) {
			imageZoomValue.textContent = String(Math.round(imageTransform.zoom * 100)) + "%";
		}
	}

	function drawEventImageOnCanvas() {
		if (!imageEditorCanvas || !imageEditorContext) {
			return;
		}

		const canvasWidth = imageEditorCanvas.width;
		const canvasHeight = imageEditorCanvas.height;

		imageEditorContext.fillStyle = "#ffffff";
		imageEditorContext.fillRect(0, 0, canvasWidth, canvasHeight);

		if (!draftEventImage) {
			return;
		}

		const imageWidth = draftEventImage.naturalWidth || draftEventImage.width;
		const imageHeight = draftEventImage.naturalHeight || draftEventImage.height;
		if (!imageWidth || !imageHeight) {
			return;
		}

		const normalizedRotation = ((imageTransform.rotation % 360) + 360) % 360;
		const isQuarterTurn = normalizedRotation === 90 || normalizedRotation === 270;
		const fittedWidth = isQuarterTurn ? imageHeight : imageWidth;
		const fittedHeight = isQuarterTurn ? imageWidth : imageHeight;
		const fitScale = Math.max(canvasWidth / fittedWidth, canvasHeight / fittedHeight);
		const finalScale = fitScale * imageTransform.zoom;

		imageEditorContext.save();
		imageEditorContext.translate(canvasWidth / 2, canvasHeight / 2);
		imageEditorContext.rotate((imageTransform.rotation * Math.PI) / 180);
		imageEditorContext.scale(finalScale, finalScale);
		imageEditorContext.drawImage(draftEventImage, -imageWidth / 2, -imageHeight / 2, imageWidth, imageHeight);
		imageEditorContext.restore();
	}

	function endCropInteraction() {
		cropInteraction = null;
		document.removeEventListener("mousemove", onCropInteractionMove);
		document.removeEventListener("mouseup", endCropInteraction);
	}

	function onCropInteractionMove(e) {
		if (!cropInteraction || !cropBox) {
			return;
		}

		const dx = e.clientX - cropInteraction.startX;
		const dy = e.clientY - cropInteraction.startY;
		const stageWidth = cropInteraction.stageWidth;
		const stageHeight = cropInteraction.stageHeight;
		const start = cropInteraction.startBox;

		if (cropInteraction.mode === "move") {
			cropBox = {
				x: clamp(start.x + dx, 0, stageWidth - start.width),
				y: clamp(start.y + dy, 0, stageHeight - start.height),
				width: start.width,
				height: start.height,
			};
			updateCropFrameStyle();
			return;
		}

		let nextX = start.x;
		let nextY = start.y;
		let nextWidth = start.width;
		let nextHeight = start.height;
		const handle = cropInteraction.handle;

		if (handle.indexOf("e") >= 0) {
			nextWidth = start.width + dx;
		}
		if (handle.indexOf("s") >= 0) {
			nextHeight = start.height + dy;
		}
		if (handle.indexOf("w") >= 0) {
			nextX = start.x + dx;
			nextWidth = start.width - dx;
		}
		if (handle.indexOf("n") >= 0) {
			nextY = start.y + dy;
			nextHeight = start.height - dy;
		}

		if (nextWidth < minCropWidth) {
			if (handle.indexOf("w") >= 0) {
				nextX -= (minCropWidth - nextWidth);
			}
			nextWidth = minCropWidth;
		}
		if (nextHeight < minCropHeight) {
			if (handle.indexOf("n") >= 0) {
				nextY -= (minCropHeight - nextHeight);
			}
			nextHeight = minCropHeight;
		}

		nextX = clamp(nextX, 0, stageWidth - minCropWidth);
		nextY = clamp(nextY, 0, stageHeight - minCropHeight);
		nextWidth = Math.min(nextWidth, stageWidth - nextX);
		nextHeight = Math.min(nextHeight, stageHeight - nextY);

		cropBox = {
			x: nextX,
			y: nextY,
			width: Math.max(minCropWidth, nextWidth),
			height: Math.max(minCropHeight, nextHeight),
		};

		updateCropFrameStyle();
	}

	function onCropFrameMouseDown(e) {
		if (!cropFrame || cropFrame.classList.contains("is-hidden") || !cropBox) {
			return;
		}

		const handleElement = e.target.closest(".crop-handle");
		const isFrameBody = e.target === cropFrame;
		if (!handleElement && !isFrameBody) {
			return;
		}

		const rect = getEditorStageRect();
		if (!rect) {
			return;
		}

		e.preventDefault();
		cropInteraction = {
			mode: handleElement ? "resize" : "move",
			handle: handleElement ? (handleElement.getAttribute("data-handle") || "") : "",
			startX: e.clientX,
			startY: e.clientY,
			stageWidth: rect.width,
			stageHeight: rect.height,
			startBox: {
				x: cropBox.x,
				y: cropBox.y,
				width: cropBox.width,
				height: cropBox.height,
			},
		};

		document.addEventListener("mousemove", onCropInteractionMove);
		document.addEventListener("mouseup", endCropInteraction);
	}

	function applyImageZoom(nextZoom) {
		const clampedZoom = Math.min(imageMaxZoom, Math.max(imageMinZoom, nextZoom));
		imageTransform.zoom = clampedZoom;

		if (imageZoomRangeInput) {
			imageZoomRangeInput.value = clampedZoom.toFixed(2);
		}

		updateImageZoomLabel();
		drawEventImageOnCanvas();
	}

	function resetImageTransformState() {
		imageTransform.zoom = 1;
		imageTransform.rotation = 0;

		if (imageZoomRangeInput) {
			imageZoomRangeInput.value = "1";
		}

		updateImageZoomLabel();
		drawEventImageOnCanvas();
	}

	function clearDraftImage() {
		draftEventImage = null;
		draftEventImageName = "";
		draftEventImageMimeType = "image/jpeg";
		setCropFrameVisible(false);
		cropBox = null;
		endCropInteraction();
		resetImageTransformState();
		setImageToolDisabledState(true);
	}

	function loadImageElementFromFile(file) {
		return new Promise(function (resolve, reject) {
			const imageUrl = URL.createObjectURL(file);
			const image = new Image();

			image.onload = function () {
				URL.revokeObjectURL(imageUrl);
				resolve(image);
			};

			image.onerror = function () {
				URL.revokeObjectURL(imageUrl);
				reject(new Error("Image load failed"));
			};

			image.src = imageUrl;
		});
	}

	function replaceUploadInputFile(file) {
		if (!uploadInput || !file) {
			return;
		}

		const dataTransfer = new DataTransfer();
		dataTransfer.items.add(file);
		uploadInput.files = dataTransfer.files;
	}

	function createEditedImageFile() {
		return new Promise(function (resolve, reject) {
			if (!imageEditorCanvas || !draftEventImage) {
				resolve(null);
				return;
			}

			const cropRect = getCropRectInCanvasCoords();
			const exportCanvas = document.createElement("canvas");
			exportCanvas.width = targetImageWidth;
			exportCanvas.height = targetImageHeight;
			const exportContext = exportCanvas.getContext("2d");
			if (!exportContext) {
				reject(new Error("Export canvas failed"));
				return;
			}

			exportContext.fillStyle = "#ffffff";
			exportContext.fillRect(0, 0, exportCanvas.width, exportCanvas.height);
			exportContext.drawImage(
				imageEditorCanvas,
				cropRect.x,
				cropRect.y,
				cropRect.width,
				cropRect.height,
				0,
				0,
				exportCanvas.width,
				exportCanvas.height
			);

			const outputMimeType = normalizeImageMimeType(draftEventImageMimeType);
			exportCanvas.toBlob(function (blob) {
				if (!blob) {
					reject(new Error("Blob conversion failed"));
					return;
				}

				const editedFile = new File([blob], buildEditedImageName(outputMimeType), {
					type: outputMimeType,
					lastModified: Date.now(),
				});

				resolve({
					file: editedFile,
					previewDataUrl: exportCanvas.toDataURL(outputMimeType, 0.92),
				});
			}, outputMimeType, 0.92);
		});
	}

	function restoreCommittedUploadSelection() {
		if (sourceEventImageFile) {
			replaceUploadInputFile(sourceEventImageFile);
			if (committedImagePreviewDataUrl) {
				setUploadPreviewFromDataUrl(committedImagePreviewDataUrl);
			} else {
				setUploadPreviewFromFile(sourceEventImageFile);
			}
			return;
		}

		uploadInput.value = "";
		clearUploadPreview();
	}

	function openEditorWithFile(file) {
		if (!file) {
			return;
		}

		loadImageElementFromFile(file)
			.then(function (imageElement) {
				draftEventImage = imageElement;
				draftEventImageName = file.name || "event-image";
				draftEventImageMimeType = normalizeImageMimeType(file.type);

				openImageEditorModalDialog();
				window.requestAnimationFrame(function () {
					resetCropFrame();
					resetImageTransformState();
					setImageToolDisabledState(false);
					drawEventImageOnCanvas();
				});
			})
			.catch(function () {
				window.alert("Khong the tai anh de chinh sua. Vui long thu lai voi anh khac.");
				clearDraftImage();
			});
	}

	function handleCancelImageEditing() {
		closeImageEditorModalDialog();
		clearDraftImage();
		restoreCommittedUploadSelection();
	}

	function handleConfirmImageEditing() {
		if (!draftEventImage || isSavingImageEdit) {
			return;
		}

		isSavingImageEdit = true;
		if (confirmImageEditBtn) {
			confirmImageEditBtn.disabled = true;
		}

		createEditedImageFile()
			.then(function (editedResult) {
				if (!editedResult || !editedResult.file) {
					throw new Error("No edited file");
				}

				const editedFile = editedResult.file;
				const previewDataUrl = editedResult.previewDataUrl || "";

				sourceEventImageFile = editedFile;
				sourceEventImageName = editedFile.name || "event-image";
				sourceEventImageMimeType = normalizeImageMimeType(editedFile.type);
				committedImagePreviewDataUrl = previewDataUrl;

				replaceUploadInputFile(editedFile);
				if (committedImagePreviewDataUrl) {
					setUploadPreviewFromDataUrl(committedImagePreviewDataUrl);
				} else {
					setUploadPreviewFromFile(editedFile);
				}
				updateOpenImageEditorButtonState();
				closeImageEditorModalDialog();
				clearDraftImage();
			})
			.catch(function () {
				window.alert("Khong the luu anh da chinh sua. Vui long thu lai.");
			})
			.finally(function () {
				isSavingImageEdit = false;
				if (confirmImageEditBtn) {
					confirmImageEditBtn.disabled = !draftEventImage;
				}
			});
	}

	function formatPrice(price) {
		if (Number(price) <= 0) {
			return "Miễn phí";
		}
		return "Từ " + Number(price).toLocaleString("vi-VN") + "d";
	}

	function syncTicketJson() {
		ticketsJsonInput.value = JSON.stringify(ticketTypes);
	}

	function setTicketFormEditingState(isEditing) {
		if (ticketFormTitle) {
			ticketFormTitle.textContent = isEditing ? "Chỉnh sửa loại vé" : "Tạo loại vé mới";
		}

		if (ticketFormSubmitBtn) {
			ticketFormSubmitBtn.textContent = isEditing ? "Lưu chỉnh sửa" : "Tạo loại vé";
		}
	}

	function openTicketFormForCreate() {
		editingTicketIndex = -1;
		resetTicketForm();
		setTicketFormEditingState(false);
		ticketTypeForm.classList.remove("is-hidden");
		ticketTypeForm.scrollIntoView({ behavior: "smooth", block: "start" });
	}

	function openTicketFormForEdit(index) {
		const ticket = ticketTypes[index];
		if (!ticket) {
			return;
		}

		editingTicketIndex = index;
		ticketNameInput.value = ticket.name || "";
		ticketQuantityInput.value = ticket.quantity || "1";
		ticketSaleStartInput.value = ticket.saleStart || "";
		ticketSaleEndInput.value = ticket.saleEnd || "";
		ticketDescInput.value = ticket.description || "";

		const isFree = Boolean(ticket.isFree) || Number(ticket.price) <= 0;
		ticketFreeInput.checked = isFree;
		if (isFree) {
			ticketPriceInput.value = "0";
			ticketPriceInput.disabled = true;
			if (suggestTicketPriceBtn) {
				suggestTicketPriceBtn.disabled = true;
			}
		} else {
			ticketPriceInput.disabled = false;
			ticketPriceInput.value = String(ticket.price || "0");
			if (suggestTicketPriceBtn) {
				suggestTicketPriceBtn.disabled = false;
			}
		}

		setTicketFormEditingState(true);
		ticketTypeForm.classList.remove("is-hidden");
		ticketTypeForm.scrollIntoView({ behavior: "smooth", block: "start" });
	}

	function closeTicketForm() {
		editingTicketIndex = -1;
		resetTicketForm();
		setTicketFormEditingState(false);
		ticketTypeForm.classList.add("is-hidden");
	}

	function renderTicketTypes() {
		ticketTypeList.innerHTML = "";

		if (!ticketTypes.length) {
			ticketTypeEmpty.style.display = "block";
			syncTicketJson();
			return;
		}

		ticketTypeEmpty.style.display = "none";

		ticketTypes.forEach(function (ticket, index) {
			const item = document.createElement("div");
			item.className = "ticket-item";
			item.innerHTML =
				'<div>' +
				'<p class="ticket-item__title">' + ticket.name + "</p>" +
				'<p class="ticket-item__meta">' +
				formatPrice(ticket.price) +
				" | Số lượng: " +
				ticket.quantity +
				" | Bán từ: " +
				ticket.saleStart.replace("T", " ") +
				"</p>" +
				"</div>" +
				'<div class="ticket-item__actions">' +
				'<button type="button" class="ticket-item__edit" data-index="' +
				index +
				'">Sửa</button>' +
				'<button type="button" class="ticket-item__remove" data-index="' +
				index +
				'">Xóa</button>' +
				"</div>";

			ticketTypeList.appendChild(item);
		});

		syncTicketJson();
	}

	function resetTicketForm() {
		ticketTypeForm.reset();
		ticketFreeInput.checked = false;
		ticketPriceInput.disabled = false;
		ticketPriceInput.value = "";
		ticketQuantityInput.value = "";
		if (suggestTicketPriceBtn) {
			suggestTicketPriceBtn.disabled = false;
			suggestTicketPriceBtn.textContent = "Gợi ý giá";
		}
	}

	function buildSuggestPricePayload() {
		const eventTypeId = eventTypeSelect ? String(eventTypeSelect.value || "").trim() : "";
		const location = (eventLocationInput && eventLocationInput.value ? eventLocationInput.value : "").trim();
		const startTime = eventStartTimeInput ? String(eventStartTimeInput.value || "").trim() : "";
		const endTime = eventEndTimeInput ? String(eventEndTimeInput.value || "").trim() : "";
		const verifyMethod = document.querySelector('input[name="verifyMethod"]:checked');
		const hasFaceReg = verifyMethod ? verifyMethod.value === "face" : true;

		const limitMode = document.querySelector('input[name="limitMode"]:checked');
		const isLimited = limitMode ? limitMode.value === "limited" : true;
		const limitQuantity = isLimited ? String(limitQuantityInput ? limitQuantityInput.value || "" : "").trim() : "";

		const ticketTypeName = (ticketNameInput && ticketNameInput.value ? ticketNameInput.value : "").trim();
		const ticketQuantity = String(ticketQuantityInput ? ticketQuantityInput.value || "" : "").trim();
		const saleStart = ticketSaleStartInput ? String(ticketSaleStartInput.value || "").trim() : "";
		const saleEnd = ticketSaleEndInput ? String(ticketSaleEndInput.value || "").trim() : "";

		return {
			eventTypeId: eventTypeId,
			location: location,
			startTime: startTime,
			endTime: endTime,
			hasFaceReg: hasFaceReg,
			limitQuantity: limitQuantity,
			ticketTypeName: ticketTypeName,
			ticketQuantity: ticketQuantity,
			saleStart: saleStart,
			saleEnd: saleEnd,
		};
	}

	function validateSuggestPriceInputs(data) {
		if (!data.eventTypeId) {
			window.alert("Vui lòng chọn thể loại sự kiện trước khi gợi ý giá.");
			if (eventTypeSelect) {
				eventTypeSelect.focus();
			}
			return false;
		}
		if (!data.location) {
			window.alert("Vui lòng nhập địa điểm tổ chức trước khi gợi ý giá.");
			if (eventLocationInput) {
				eventLocationInput.focus();
			}
			return false;
		}
		if (!data.startTime || !data.endTime) {
			window.alert("Vui lòng chọn thời gian bắt đầu/kết thúc trước khi gợi ý giá.");
			if (eventStartTimeInput) {
				eventStartTimeInput.focus();
			}
			return false;
		}
		if (!data.ticketTypeName) {
			window.alert("Vui lòng nhập tên vé trước khi gợi ý giá.");
			if (ticketNameInput) {
				ticketNameInput.focus();
			}
			return false;
		}
		if (!data.ticketQuantity) {
			window.alert("Vui lòng nhập tổng số lượng vé trước khi gợi ý giá.");
			if (ticketQuantityInput) {
				ticketQuantityInput.focus();
			}
			return false;
		}
		if (!data.saleStart || !data.saleEnd) {
			window.alert("Vui lòng chọn đầy đủ thời gian bán vé trước khi gợi ý giá.");
			if (ticketSaleStartInput) {
				ticketSaleStartInput.focus();
			}
			return false;
		}

		if (new Date(data.endTime) < new Date(data.startTime)) {
			window.alert("Thời gian kết thúc phải lớn hơn hoặc bằng thời gian bắt đầu.");
			return false;
		}
		if (new Date(data.saleEnd) < new Date(data.saleStart)) {
			window.alert("Thời gian kết thúc bán vé phải lớn hơn hoặc bằng thời gian bắt đầu.");
			return false;
		}
		if (Number(data.ticketQuantity) <= 0) {
			window.alert("Số lượng vé phải lớn hơn 0.");
			return false;
		}
		if (data.limitQuantity && Number(data.limitQuantity) <= 0) {
			window.alert("Giới hạn số lượng vé trên mỗi tài khoản phải lớn hơn 0.");
			if (limitQuantityInput) {
				limitQuantityInput.focus();
			}
			return false;
		}

		return true;
	}

	function setSuggestButtonLoading(isLoading) {
		if (!suggestTicketPriceBtn) {
			return;
		}
		suggestTicketPriceBtn.disabled = Boolean(isLoading);
		suggestTicketPriceBtn.textContent = isLoading ? "Đang gợi ý..." : "Gợi ý giá";
	}

	function toggleLimitQuantity() {
		const selected = document.querySelector('input[name="limitMode"]:checked');
		const isLimited = selected && selected.value === "limited";
		limitQtyBox.style.display = isLimited ? "inline-flex" : "none";
		limitQuantityInput.disabled = !isLimited;
	}

	function updateFloatingEventActions() {
		if (!floatingEventActions) {
			return;
		}

		const shouldShow = window.scrollY > 180;
		floatingEventActions.classList.toggle("is-visible", shouldShow);
		floatingEventActions.setAttribute("aria-hidden", shouldShow ? "false" : "true");
	}

	function autoDismissFlashAlerts() {
		if (!flashWrap || !flashAlerts.length) {
			return;
		}

		flashAlerts.forEach(function (alertEl, index) {
			window.setTimeout(function () {
				if (!alertEl || !alertEl.parentNode) {
					return;
				}

				alertEl.style.transition = "opacity 250ms ease, transform 250ms ease";
				alertEl.style.opacity = "0";
				alertEl.style.transform = "translateY(-4px)";

				window.setTimeout(function () {
					if (alertEl.parentNode) {
						alertEl.remove();
					}
					if (!flashWrap.querySelector(".alert")) {
						flashWrap.remove();
					}
				}, 260);
			}, 5000 + index * 80);
		});
	}

	if (uploadInput) {
		uploadInput.addEventListener("change", function () {
			const file = uploadInput.files && uploadInput.files[0];
			if (!file) {
				restoreCommittedUploadSelection();
				return;
			}

			if (!file.type || !file.type.startsWith("image/")) {
				window.alert("Vui long chon file anh hop le.");
				restoreCommittedUploadSelection();
				return;
			}

			openEditorWithFile(file);
		});
	}

	limitModeInputs.forEach(function (input) {
		input.addEventListener("change", toggleLimitQuantity);
	});

	if (imageZoomRangeInput) {
		imageZoomRangeInput.addEventListener("input", function () {
			applyImageZoom(Number(imageZoomRangeInput.value || "1"));
		});
	}

	if (zoomOutBtn) {
		zoomOutBtn.addEventListener("click", function () {
			applyImageZoom(imageTransform.zoom - imageZoomStep);
		});
	}

	if (zoomInBtn) {
		zoomInBtn.addEventListener("click", function () {
			applyImageZoom(imageTransform.zoom + imageZoomStep);
		});
	}

	if (rotateLeftBtn) {
		rotateLeftBtn.addEventListener("click", function () {
			imageTransform.rotation -= 90;
			drawEventImageOnCanvas();
		});
	}

	if (rotateRightBtn) {
		rotateRightBtn.addEventListener("click", function () {
			imageTransform.rotation += 90;
			drawEventImageOnCanvas();
		});
	}

	if (resetImageTransformBtn) {
		resetImageTransformBtn.addEventListener("click", function () {
			resetImageTransformState();
		});
	}

	if (openImageEditorBtn) {
		openImageEditorBtn.addEventListener("click", function () {
			if (!sourceEventImageFile) {
				return;
			}
			openEditorWithFile(sourceEventImageFile);
		});
	}

	if (confirmImageEditBtn) {
		confirmImageEditBtn.addEventListener("click", handleConfirmImageEditing);
	}

	if (cancelImageEditBtn) {
		cancelImageEditBtn.addEventListener("click", handleCancelImageEditing);
	}

	if (closeImageEditorBtn) {
		closeImageEditorBtn.addEventListener("click", handleCancelImageEditing);
	}

	if (imageEditorModal) {
		imageEditorModal.addEventListener("click", function (e) {
			const closeTrigger = e.target.closest("[data-close-image-editor]");
			if (closeTrigger) {
				handleCancelImageEditing();
			}
		});
	}

	if (cropFrame) {
		cropFrame.addEventListener("mousedown", onCropFrameMouseDown);
	}

	document.addEventListener("keydown", function (e) {
		if (e.key !== "Escape") {
			return;
		}
		if (!imageEditorModal || imageEditorModal.classList.contains("is-hidden")) {
			return;
		}
		handleCancelImageEditing();
	});

	qtyMinusBtn.addEventListener("click", function () {
		const current = Number(limitQuantityInput.value || "0");
		limitQuantityInput.value = String(Math.max(1, current - 1));
	});

	qtyPlusBtn.addEventListener("click", function () {
		const current = Number(limitQuantityInput.value || "0");
		limitQuantityInput.value = String(current + 1);
	});

	openTicketFormBtn.addEventListener("click", function () {
		openTicketFormForCreate();
	});

	cancelTicketBtn.addEventListener("click", function () {
		closeTicketForm();
	});

	ticketFreeInput.addEventListener("change", function () {
		if (ticketFreeInput.checked) {
			ticketPriceInput.value = "0";
			ticketPriceInput.disabled = true;
			if (suggestTicketPriceBtn) {
				suggestTicketPriceBtn.disabled = true;
			}
		} else {
			ticketPriceInput.disabled = false;
			if (suggestTicketPriceBtn) {
				suggestTicketPriceBtn.disabled = false;
			}
		}
	});

	if (suggestTicketPriceBtn) {
		suggestTicketPriceBtn.addEventListener("click", function () {
			if (ticketFreeInput && ticketFreeInput.checked) {
				ticketPriceInput.value = "0";
				return;
			}

			const data = buildSuggestPricePayload();
			if (!validateSuggestPriceInputs(data)) {
				return;
			}

			setSuggestButtonLoading(true);

			window
				.fetch("/api/organizer/ticket-types/suggest-price", {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
					},
					body: JSON.stringify({
						event: {
							eventTypeId: Number(data.eventTypeId),
							location: data.location,
							startTime: data.startTime,
							endTime: data.endTime,
							hasFaceReg: Boolean(data.hasFaceReg),
							limitQuantity: data.limitQuantity ? Number(data.limitQuantity) : null,
						},
						tickets: [
							{
								ticketTypeName: data.ticketTypeName,
								ticketQuantity: Number(data.ticketQuantity),
								saleStart: data.saleStart,
								saleEnd: data.saleEnd,
							},
						],
					}),
				})
				.then(function (res) {
					if (res.status === 401) {
						throw new Error("unauthorized");
					}
					return res
						.json()
						.then(function (json) {
							return { ok: res.ok, status: res.status, json: json };
						})
						.catch(function () {
							return { ok: res.ok, status: res.status, json: null };
						});
				})
				.then(function (result) {
					if (!result.ok) {
						const message = result && result.json && result.json.message ? result.json.message : "Không thể gợi ý giá vé.";
						window.alert(message);
						return;
					}

					const suggestions = result.json && result.json.suggestions ? result.json.suggestions : [];
					const first = suggestions && suggestions.length ? suggestions[0] : null;
					if (!first || typeof first.suggestedPrice !== "number") {
						window.alert("Không nhận được giá gợi ý hợp lệ.");
						return;
					}

					ticketPriceInput.disabled = false;
					if (ticketFreeInput) {
						ticketFreeInput.checked = false;
					}
					ticketPriceInput.value = String(first.suggestedPrice);
				})
				.catch(function (err) {
					if (String(err && err.message) === "unauthorized") {
						window.alert("Bạn cần đăng nhập tài khoản nhà tổ chức để dùng chức năng này.");
						return;
					}
					window.alert("Không thể gợi ý giá vé. Vui lòng thử lại.");
				})
				.finally(function () {
					setSuggestButtonLoading(false);
				});
		});
	}

	ticketTypeForm.addEventListener("submit", function (e) {
		e.preventDefault();
		const rawTicketPrice = (ticketPriceInput.value || "").trim();
		const rawTicketQuantity = (ticketQuantityInput.value || "").trim();

		const payload = {
			name: (ticketNameInput.value || "").trim(),
			isFree: ticketFreeInput.checked,
			price: ticketFreeInput.checked ? "0" : rawTicketPrice,
			quantity: rawTicketQuantity,
			saleStart: ticketSaleStartInput.value,
			saleEnd: ticketSaleEndInput.value,
			description: (ticketDescInput.value || "").trim(),
		};

		if (!payload.name) {
			window.alert("Vui lòng nhập tên vé.");
			return;
		}
		if (!payload.saleStart || !payload.saleEnd) {
			window.alert("Vui lòng chọn đầy đủ thời gian bán vé.");
			return;
		}
		if (!payload.isFree && !rawTicketPrice) {
			window.alert("Vui lòng nhập giá vé.");
			return;
		}
		if (!rawTicketQuantity) {
			window.alert("Vui lòng nhập tổng số lượng vé.");
			return;
		}
		if (new Date(payload.saleEnd) < new Date(payload.saleStart)) {
			window.alert("Thời gian kết thúc bán vé phải lớn hơn hoặc bằng thời gian bắt đầu.");
			return;
		}
		if (Number(payload.quantity) <= 0) {
			window.alert("Số lượng vé phải lớn hơn 0.");
			return;
		}
		if (Number(payload.price) < 0) {
			window.alert("Giá vé không hợp lệ.");
			return;
		}

		if (editingTicketIndex >= 0) {
			ticketTypes[editingTicketIndex] = payload;
		} else {
			ticketTypes.push(payload);
		}

		renderTicketTypes();
		closeTicketForm();
	});

	ticketTypeList.addEventListener("click", function (e) {
		const editBtn = e.target.closest(".ticket-item__edit");
		if (editBtn) {
			const editIndex = Number(editBtn.getAttribute("data-index"));
			if (Number.isNaN(editIndex)) {
				return;
			}

			openTicketFormForEdit(editIndex);
			return;
		}

		const removeBtn = e.target.closest(".ticket-item__remove");
		if (!removeBtn) {
			return;
		}

		const index = Number(removeBtn.getAttribute("data-index"));
		if (Number.isNaN(index)) {
			return;
		}

		ticketTypes.splice(index, 1);
		if (editingTicketIndex === index) {
			closeTicketForm();
		} else if (editingTicketIndex > index) {
			editingTicketIndex -= 1;
		}

		renderTicketTypes();
	});

	eventForm.addEventListener("submit", function (e) {
		if (descriptionEditor) {
			const html = descriptionEditor.root.innerHTML.trim();
			descriptionHiddenInput.value = html === "<p><br></p>" ? "" : html;
		} else {
			descriptionHiddenInput.value = "";
		}

		const eventTitle = (eventTitleInput && eventTitleInput.value ? eventTitleInput.value : "").trim();
		if (!eventTitle) {
			e.preventDefault();
			window.alert("Vui lòng nhập tên sự kiện.");
			if (eventTitleInput) {
				eventTitleInput.focus();
			}
			return;
		}

		const eventLocation = (eventLocationInput && eventLocationInput.value ? eventLocationInput.value : "").trim();
		if (!eventLocation) {
			e.preventDefault();
			window.alert("Vui lòng nhập địa điểm tổ chức.");
			if (eventLocationInput) {
				eventLocationInput.focus();
			}
			return;
		}

		const eventTypeId = eventTypeSelect ? String(eventTypeSelect.value || "").trim() : "";
		if (!eventTypeId) {
			e.preventDefault();
			window.alert("Vui lòng chọn thể loại sự kiện.");
			if (eventTypeSelect) {
				eventTypeSelect.focus();
			}
			return;
		}

		const eventDescription = (descriptionHiddenInput && descriptionHiddenInput.value ? descriptionHiddenInput.value : "").trim();
		if (!eventDescription) {
			e.preventDefault();
			window.alert("Vui lòng nhập thông tin sự kiện.");
			return;
		}

		const start = eventStartTimeInput ? String(eventStartTimeInput.value || "").trim() : "";
		const end = eventEndTimeInput ? String(eventEndTimeInput.value || "").trim() : "";
		if (!start || !end) {
			e.preventDefault();
			window.alert("Vui lòng nhập đầy đủ thời gian bắt đầu và kết thúc.");
			return;
		}

		const selectedLimitMode = document.querySelector('input[name="limitMode"]:checked');
		if (selectedLimitMode && selectedLimitMode.value === "limited") {
			const rawLimitQuantity = (limitQuantityInput && limitQuantityInput.value ? limitQuantityInput.value : "").trim();
			if (!rawLimitQuantity) {
				e.preventDefault();
				window.alert("Vui lòng nhập giới hạn số lượng vé trên mỗi tài khoản.");
				if (limitQuantityInput) {
					limitQuantityInput.focus();
				}
				return;
			}
		}

		if (!ticketTypes.length) {
			e.preventDefault();
			window.alert("Vui lòng tạo ít nhất một loại vé trước khi tạo sự kiện.");
			return;
		}

		if (start && end && new Date(end) < new Date(start)) {
			e.preventDefault();
			window.alert("Thời gian kết thúc sự kiện phải lớn hơn hoặc bằng thời gian bắt đầu.");
			return;
		}

		if (imageEditorModal && !imageEditorModal.classList.contains("is-hidden")) {
			e.preventDefault();
			window.alert("Vui lòng nhấn Đồng ý hoặc Hủy trên form chỉnh sửa ảnh trước khi tạo sự kiện.");
			return;
		}

		syncTicketJson();
	});

	eventForm.addEventListener("reset", function () {
		window.setTimeout(function () {
			ticketTypes.splice(0, ticketTypes.length);
			renderTicketTypes();
			closeTicketForm();

			if (descriptionEditor) {
				descriptionEditor.setContents([]);
			}
			descriptionHiddenInput.value = "";

			sourceEventImageFile = null;
			sourceEventImageName = "";
			sourceEventImageMimeType = "image/jpeg";
			committedImagePreviewDataUrl = "";
			clearDraftImage();
			closeImageEditorModalDialog();
			uploadInput.value = "";
			clearUploadPreview();
			updateOpenImageEditorButtonState();
			isSavingImageEdit = false;

			limitQuantityInput.value = "";
			const limitedRadio = document.querySelector('input[name="limitMode"][value="limited"]');
			if (limitedRadio) {
				limitedRadio.checked = true;
			}
			toggleLimitQuantity();
			updateFloatingEventActions();
		}, 0);
	});

	window.addEventListener("scroll", updateFloatingEventActions, { passive: true });
	window.addEventListener("resize", updateFloatingEventActions);

	setImageToolDisabledState(true);
	updateOpenImageEditorButtonState();
	clearUploadPreview();
	updateImageZoomLabel();
	drawEventImageOnCanvas();
	toggleLimitQuantity();
	setTicketFormEditingState(false);
	updateFloatingEventActions();
	renderTicketTypes();
	autoDismissFlashAlerts();
});
