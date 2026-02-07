import pypdfium2 as pdfium
import sys

pdf_path = sys.argv[1]
output_path = sys.argv[2]

pdf = pdfium.PdfDocument(pdf_path)
page = pdf[0]
image = page.render(scale=2.0)
pil_image = image.to_pil()
pil_image.save(output_path)
print(f"Converted {pdf_path} to {output_path}")
