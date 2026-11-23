"""Lightweight spawn targets used by the pinned BabelDOC macOS worker.

Each child needs only MuPDF. BabelDOC's parent still owns timeouts, recovery,
output validation and cleanup for both native operations.
"""


def subset_fonts(source, destination):
    import pymupdf

    with pymupdf.open(source) as document:
        document.subset_fonts(fallback=False)
        document.save(destination)


def save_pdf(source, destination, garbage, deflate, clean, deflate_fonts, linear):
    import pymupdf

    with pymupdf.open(source) as document:
        document.save(destination, garbage=garbage, deflate=deflate,
                      clean=clean, deflate_fonts=deflate_fonts, linear=linear)
