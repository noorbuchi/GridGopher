"""
Test cases for sheet_collector Module
"""

import pathlib

from gatorgopher import sheet_collector


def test_get_yaml_files_empty():
    collector = sheet_collector.SheetCollector()
    files_list = list(collector.get_yaml_files(pathlib.Path("config")))
    assert files_list == []


def test_get_yaml_files_exists():
    # FIXME: likely to cause issues later when files change, should use temp
    # files instead
    collector = sheet_collector.SheetCollector()
    files_list = [
        str(path)
        for path in collector.get_yaml_files(pathlib.Path("config/sheet_sources"))
    ]
    assert files_list == [
        "config/sheet_sources/file3.yaml",
        "config/sheet_sources/file2.yaml",
        "config/sheet_sources/file1.yaml",
    ]
