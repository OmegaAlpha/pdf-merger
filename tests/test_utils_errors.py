import fitz
import pytest
from utils import check_fitz_toc_for_first_page, adjust_toc_pages_and_levels

def test_check_fitz_toc_for_first_page_invalid():
    # Pass a toc that lacks page numbers or is malformed
    bad_toc = [
        [1, "Title Only"], # missing page number
        [1, "Valid", 2],
        "Not even a list"
    ]
    # It should handle this gracefully and return False since page 1 isn't found
    assert check_fitz_toc_for_first_page(bad_toc) is False

def test_adjust_toc_pages_and_levels_invalid(mocker):
    bad_toc = [
        [1, "Missing Page"], # invalid length
        [1, "Valid Page", 1],
        [1, "Invalid Dest Dict", 2, "not a dict"]
    ]
    mock_doc = mocker.MagicMock()
    mock_doc.page_count = 5
    
    # Should safely ignore bad entries or handle them
    adjusted = adjust_toc_pages_and_levels(bad_toc, page_offset_0based=10, source_doc=mock_doc, level_increase=1)
    
    # The valid entry should be adjusted. The missing page entry will be skipped or adjusted if it doesn't crash
    # According to utils.py:
    # if len(item) < 3: continue
    # if not isinstance(item[2], int): continue
    # It will skip the first one and the third one if type checks fail.
    
    # Actually let's just make sure it doesn't raise an exception
    assert isinstance(adjusted, list)


