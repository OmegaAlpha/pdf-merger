import os
import fitz
import traceback
from typing import List, Tuple

from model import PDFDocument
from utils import check_fitz_toc_for_first_page, adjust_toc_pages_and_levels

def merge_pdfs_engine(pdf_list: List[PDFDocument], output_path: str) -> Tuple[bool, str]:
    """
    Core engine to merge PDF files.
    Returns (success_bool, message).
    """
    if not pdf_list:
        return False, "No PDFs to merge."

    merged_doc = fitz.open()
    final_toc = []
    current_page_offset = 0
    success_count = 0
    error_files = []
    toc_error_files = []

    try:
        for pdf_item in pdf_list:
            pdf_path = pdf_item.file_path
            name = pdf_item.name
            doc_to_add = None
            try:
                doc_to_add = fitz.open(pdf_path)
                num_pages_in_source = doc_to_add.page_count
                if num_pages_in_source == 0:
                    error_files.append(f"{name} (no pages)")
                    doc_to_add.close()
                    continue

                source_toc = None
                has_first_page_bookmark = False
                try:
                    source_toc = doc_to_add.get_toc(simple=False)
                    if source_toc:
                        has_first_page_bookmark = check_fitz_toc_for_first_page(source_toc)
                except Exception:
                    source_toc = None

                # Build TOC
                try:
                    if has_first_page_bookmark and source_toc:
                        adjusted_toc = adjust_toc_pages_and_levels(
                            source_toc, current_page_offset, doc_to_add, level_increase=0
                        )
                        if adjusted_toc:
                            final_toc.extend(adjusted_toc)
                        else:
                            toc_error_files.append(name)
                    else:
                        bookmark_title = os.path.splitext(name)[0]
                        file_page_1based = current_page_offset + 1
                        file_dest = {
                            "kind": 1,
                            "to": fitz.Point(0, 0),
                            "page": current_page_offset,
                            "zoom": 0.0,
                        }
                        file_entry = [1, bookmark_title, file_page_1based, file_dest]
                        final_toc.append(file_entry)

                        if source_toc:
                            adjusted_nested_toc = adjust_toc_pages_and_levels(
                                source_toc, current_page_offset, doc_to_add, level_increase=1
                            )
                            if adjusted_nested_toc:
                                final_toc.extend(adjusted_nested_toc)
                            else:
                                toc_error_files.append(name)
                except Exception as e:
                    traceback.print_exc()
                    toc_error_files.append(name)

                # Insert pages
                merged_doc.insert_pdf(
                    doc_to_add,
                    from_page=0,
                    to_page=num_pages_in_source - 1,
                    start_at=current_page_offset,
                )
                doc_to_add.close()
                success_count += 1
                current_page_offset += num_pages_in_source

            except Exception as process_error:
                traceback.print_exc()
                error_files.append(f"{name} ({type(process_error).__name__})")
                if doc_to_add and not getattr(doc_to_add, "is_closed", True):
                    try:
                        doc_to_add.close()
                    except:
                        pass

        if success_count > 0:
            if final_toc:
                valid_toc = []
                for entry in final_toc:
                    if (
                        isinstance(entry, list)
                        and len(entry) >= 3
                        and isinstance(entry[0], int)
                        and entry[0] >= 1
                        and isinstance(entry[1], str)
                        and entry[1].strip()
                        and isinstance(entry[2], int)
                        and entry[2] >= 1
                        and (len(entry) == 3 or isinstance(entry[3], dict))
                    ):
                        valid_toc.append(entry)

                if valid_toc:
                    try:
                        merged_doc.set_toc(valid_toc)
                    except Exception as e:
                        traceback.print_exc()

            try:
                merged_doc.save(output_path, garbage=4, deflate=True)
                final_msg = f"Merged {success_count} PDF(s) to {output_path}"
                if error_files:
                    final_msg += f" ({len(error_files)} error(s))."
                if toc_error_files:
                    final_msg += f" Bookmark errors in {len(toc_error_files)} file(s)."
                return True, final_msg
            except Exception as save_error:
                traceback.print_exc()
                return False, f"ERROR saving merged file: {save_error}"

        elif error_files:
            return False, f"Merge failed. {len(error_files)} file(s) had errors."
        else:
            return False, "No valid PDFs were available to merge."

    except Exception as merge_error:
        traceback.print_exc()
        return False, f"FATAL Merge Error: {merge_error}"
    finally:
        if merged_doc is not None:
            try:
                if not getattr(merged_doc, "is_closed", True):
                    merged_doc.close()
            except Exception:
                pass
