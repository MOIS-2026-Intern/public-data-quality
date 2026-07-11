from __future__ import annotations

SUPPORTED_DATASET_SUFFIXES = {
    ".csv",
    ".tsv",
    ".txt",
    ".xlsx",
    ".xls",
    ".json",
    ".jsonl",
    ".xml",
}
SUPPORTED_ARCHIVE_SUFFIXES = {".zip"}
SUPPORTED_UPLOAD_SUFFIXES = SUPPORTED_DATASET_SUFFIXES | SUPPORTED_ARCHIVE_SUFFIXES
SUPPORTED_URL_LIST_SUFFIXES = {".txt", ".csv", ".tsv", ".xlsx", ".xls"}
REMOTE_TEXT_SUFFIXES = {".csv", ".tsv", ".txt"}
TEXT_DATASET_ENCODINGS = ("utf-8-sig", "utf-8", "cp949", "euc-kr", "utf-16-le", "utf-16-be")

REMOTE_TIMEOUT_SECONDS = 60
REMOTE_REQUEST_USER_AGENT = "LDQ-GPT/1.0"
URL_LIST_MAX_EXPANSION_DEPTH = 3

PUBLIC_DATA_PORTAL_DOWNLOAD_API_PATH = "/tcs/dss/selectFileDataDownload.do"
PUBLIC_DATA_PORTAL_FILE_DOWNLOAD_PATH = "/cmm/cmm/fileDownload.do"

TRAILING_URL_PUNCTUATION = ".,;:)]}>"
URL_LIST_HEADER_VALUES = {
    "url",
    "urls",
    "link",
    "links",
    "dataurl",
    "dataseturl",
    "fileurl",
    "downloadurl",
    "링크",
    "url링크",
    "다운로드url",
    "파일url",
}

RECORD_CONTAINER_KEYS = (
    "records",
    "record",
    "rows",
    "row",
    "items",
    "item",
    "data",
    "result",
    "results",
    "list",
    "body",
    "response",
)
