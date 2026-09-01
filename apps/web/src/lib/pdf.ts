import html2canvas from "html2canvas-pro";
import jsPDF from "jspdf";

const A4_WIDTH_MM = 210;
const A4_HEIGHT_MM = 297;
const MARGIN_MM = 8;

/**
 * Render an HTML element to a multi-page A4 PDF and trigger a download.
 */
export async function downloadPdf(
  element: HTMLElement,
  filename: string,
): Promise<void> {
  const canvas = await html2canvas(element, {
    scale: 2,
    useCORS: true,
    allowTaint: true,
    backgroundColor: "#ffffff",
    logging: false,
  });

  const contentWidth = A4_WIDTH_MM - MARGIN_MM * 2;
  const imgWidth = contentWidth;
  const imgHeight = (canvas.height * imgWidth) / canvas.width;
  const pageHeight = A4_HEIGHT_MM - MARGIN_MM * 2;

  const pdf = new jsPDF("p", "mm", "a4");

  let heightLeft = imgHeight;
  let position = MARGIN_MM;

  const imgData = canvas.toDataURL("image/png");

  // First page
  pdf.addImage(imgData, "PNG", MARGIN_MM, position, imgWidth, imgHeight);
  heightLeft -= pageHeight;

  // Additional pages
  while (heightLeft > 0) {
    position = -(pageHeight * (Math.ceil(imgHeight / pageHeight) - 1)) + MARGIN_MM;
    pdf.addPage();
    pdf.addImage(imgData, "PNG", MARGIN_MM, position - heightLeft + pageHeight, imgWidth, imgHeight);
    heightLeft -= pageHeight;
  }

  pdf.save(filename);
}

/**
 * Render multiple report card elements to a single multi-page PDF.
 */
export async function downloadBulkPdf(
  elements: HTMLElement[],
  filename: string,
): Promise<void> {
  const pdf = new jsPDF("p", "mm", "a4");
  const contentWidth = A4_WIDTH_MM - MARGIN_MM * 2;
  const pageHeight = A4_HEIGHT_MM - MARGIN_MM * 2;

  for (let i = 0; i < elements.length; i++) {
    const canvas = await html2canvas(elements[i], {
      scale: 2,
      useCORS: true,
      allowTaint: true,
      backgroundColor: "#ffffff",
      logging: false,
    });

    const imgWidth = contentWidth;
    const imgHeight = (canvas.height * imgWidth) / canvas.width;
    const imgData = canvas.toDataURL("image/png");

    let heightLeft = imgHeight;
    let position = MARGIN_MM;

    if (i > 0) pdf.addPage();

    // First page of this card
    pdf.addImage(imgData, "PNG", MARGIN_MM, position, imgWidth, imgHeight);
    heightLeft -= pageHeight;

    // Additional pages for this card
    while (heightLeft > 0) {
      pdf.addPage();
      const pageOffset = -(pageHeight * Math.floor((imgHeight - heightLeft) / pageHeight));
      pdf.addImage(imgData, "PNG", MARGIN_MM, pageOffset + MARGIN_MM, imgWidth, imgHeight);
      heightLeft -= pageHeight;
    }
  }

  pdf.save(filename);
}
