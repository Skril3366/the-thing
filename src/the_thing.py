import argparse
from jsonpath_ng import jsonpath, parse
import asyncio
import json
import os
import re
import shutil
import time
from enum import Enum
from pathlib import Path

import pymupdf
from fuzzywuzzy import fuzz
from transformers import AutoTokenizer

from common import prompts
from common.file import sanitize_file_name
from common.config import (EXTRACTED_TEXT_FOLDER, JSON_REFERENCE_KEY_FILE,
                           MAX_API_TOKENS_ALLOWED, MAX_CHARS_IN_FILE_NAME, MAX_CONCURRENT_REQUESTS,
                           NOTES_OUTPUT_FOLDER, PDF_PAPERS_FOLDER, PDF_PAPERS_RAW_FOLDER,
                           TOKEN_COUNT_FOLDER, TOKENIZER_MODEL)
from common.model import Message, Model, Request, Role, call


class FileType(Enum):
    TXT = ".txt"
    MARKDOWN = ".md"
    PDF = ".pdf"
    TOKEN = ".token"
    FOLDER = ""


def convert_to_txt(filename: str):
    file_path = os.path.join(PDF_PAPERS_FOLDER, filename + FileType.PDF.value)
    with pymupdf.open(file_path) as doc:
        return "\n".join(page.get_text("text") for page in doc)

def flatten_folder(source_folder, destination_folder):
    """
    Recursively flattens the source folder by moving all files to the destination folder.

    Args:
    source_folder (str): Path to the folder to be flattened
    destination_folder (str): Path to the folder where files will be moved
    """
    os.makedirs(destination_folder, exist_ok = True)

    existing_files = filenames_in_folder(destination_folder, None)

    for root, dirs, files in os.walk(source_folder):
        for file in files:
            if Path(file).stem in existing_files:
                print(f"Skipping, already copied before: {file}")
                continue
            source_path = os.path.join(root, file)
            base, extension = os.path.splitext(file)
            counter = 1
            destination_path = os.path.join(destination_folder, file)
            shutil.copy(source_path, destination_path)


def filenames_in_folder(folder: str, filetype: FileType | None) -> list[str]:
    """Returns filenames without extensions of all files in the given folder
    If `filetype` is None returns all files, if not - only specific extension
    """
    only_names = []
    for f in os.listdir(folder):
        path_str = os.path.join(folder, f)
        path = Path(f)
        match filetype:
            case FileType.FOLDER:
                if os.path.isdir(path_str):
                    only_names.append(f)
            case None:
                if os.path.isdir(path_str):
                    only_names.append(f)
                else:
                    only_names.append(Path(f).stem)
            case _:
                if os.path.isfile(path_str) and path.suffix == filetype.value:
                    only_names.append(path.stem)
    return only_names


def logProgress(iteration, total_iterations, message):
    print(f"{iteration}/{total_iterations} | {message}")


def ask_user(question: str) -> bool:
    result: bool | None = None
    while result is None:
        answer = input(f"{question} (yes/y or no/n): ").strip().lower()
        if answer.lower() in ("yes", "y"):
            result = True
        elif answer.lower() in ("no", "n"):
            result = False
    return result


def clean_from_code_blocks(text: str) -> str:
    pattern = r"```.*"
    return re.sub(pattern, "", text)


def format_time(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s or not parts:
        parts.append(f"{s}s")
    return "".join(parts)


def format_note(title_and_body: str, paper_note: str) -> str:
    return f"""{title_and_body}

## References

- [[{paper_note}]]"""


def find_reference_key(paper_title: str, json_map: list[dict[str, str]]) -> str | None:
    title_match: str = ""
    match_percentage: int = 0

    for elements in json_map:
        maybeId = elements.get("id")
        maybeTitle = elements.get("title")
        if maybeTitle and maybeId:
            p = fuzz.token_set_ratio(maybeTitle, paper_title)
            if p > match_percentage:
                match_percentage = p
                title_match = maybeId

    if match_percentage < 80:
        return None
    return title_match

def find_most_similar(key: str, values: list[str]) -> str | None:
    best_match: str = ""
    match_percentage: int = 0

    for element in values:
            p = fuzz.token_set_ratio(element, key)
            if p > match_percentage:
                match_percentage = p
                best_match = element

    if match_percentage < 90:
        return None
    return best_match


def extract_or(json: dict, expr_str: str, default: str | None = None):
        res = parse(expr_str).find(json)
        if res and len(res) > 0:
            return res[0].value
        return default


def reference_key_map_generator(items: list[dict[str, str]], pdf_titles: list[str]) -> dict[str, str]:

    mapping = {}
    for item in items:
        author_surname_part = extract_or(item, "$.author[0].literal")
        author_surname_part = extract_or(item, "$.author[0].family", author_surname_part)

        et_al_part = None
        maybe_authors = extract_or(item, "$.author", None)
        if maybe_authors and len(maybe_authors) == 2:
            et_al_part = extract_or(item, "$.author[1].literal")
            et_al_part = extract_or(item, "$.author[1].family", et_al_part)
            if et_al_part:
                et_al_part = f"and {et_al_part}"
        elif maybe_authors and len(maybe_authors) > 2:
            et_al_part = "et al."

        full_author_part: str = ""
        if author_surname_part:
            full_author_part = author_surname_part
            if et_al_part:
                full_author_part += " " + et_al_part
            full_author_part += " - "

        maybe_issued = extract_or(item, "$.issued.date-parts[0][0]")
        year_part: str = ""
        if maybe_issued:
            year_part = f"{maybe_issued} - "

        maybe_paper_title = extract_or(item, "$.title")
        title_part: str = ""
        if maybe_paper_title:
            title_part = maybe_paper_title
        else:
            print("ERROR | Not paper title!!!")

        full_pdf_paper_name: str = full_author_part + year_part + title_part

        full_pdf_paper_name = sanitize_file_name(full_pdf_paper_name[:MAX_CHARS_IN_FILE_NAME])

        maybe_reference_key = extract_or(item, "$.id")
        if maybe_reference_key:
            actual_pdf = find_most_similar(full_pdf_paper_name, pdf_titles)
            if actual_pdf:
                mapping[actual_pdf] = maybe_reference_key
        else:
            print("ERROR | Not found reference key!!!")

    return mapping



async def notes_for_paper(iteration, reference_key, total_count, semaphore):
    async with semaphore:
        start_time = time.time()
        path_for_notes = os.path.join(NOTES_OUTPUT_FOLDER, reference_key)
        os.makedirs(path_for_notes, exist_ok=True)

        number_of_notes_in_folder = len(
            filenames_in_folder(path_for_notes, FileType.MARKDOWN)
        )
        if number_of_notes_in_folder > 0:
            logProgress(
                iteration,
                total_count,
                f"Skipped, already has {number_of_notes_in_folder} notes",
            )
            return
        logProgress(
            iteration,
            total_count,
            f"Started separating into ideas {reference_key}",
        )

        txt_file_location = os.path.join(
            EXTRACTED_TEXT_FOLDER, reference_key + FileType.TXT.value
        )
        with open(txt_file_location, "r") as f:
            txt_content = f.read()

        request = Request(
            model=Model.GeminiFlash,
            messages=[
                Message(Role.SYSTEM, prompts.system_prompt()),
                Message(Role.USER, prompts.idea_separation(txt_content)),
            ],
        )
        result = await call(request)
        try:
            content = result["choices"][0]["message"]["content"]
        except KeyError:
            print(f"Got key for the API call for file: {reference_key}")
            print(result)
            raise Exception("No content field found in API answer, should never happen")

        content_cleaned = clean_from_code_blocks(content)

        individual_notes = [t.strip() for t in content_cleaned.split("---")]

        for note in individual_notes:
            lines = note.splitlines()
            if len(lines) == 0 or not lines[0].startswith("# "):
                continue
            title = lines[0].replace("# ", "")
            note_path = os.path.join(path_for_notes, title + FileType.MARKDOWN.value)
            formatted_note_content = format_note(note, reference_key)
            with open(note_path, "w") as f:
                f.write(formatted_note_content)

        elapsed_time = time.time() - start_time
        logProgress(
            iteration,
            total_count,
            f"Processed {len(individual_notes)} notes created in {format_time(elapsed_time)}",
        )


async def create_notes():
    os.makedirs(NOTES_OUTPUT_FOLDER, exist_ok=True)
    txt_files = filenames_in_folder(EXTRACTED_TEXT_FOLDER, FileType.TXT)

    inputs = [(i + 1, t, len(txt_files)) for i, t in enumerate(txt_files)]

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    tasks = [notes_for_paper(i, t, l, semaphore) for i, t, l in inputs]
    await asyncio.gather(*tasks)


def main():
    ################ Parsing arguments #############################
    parser = argparse.ArgumentParser(
        description="CLI App that creates atomic notes out of scientific pdf papers"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Execute everything without asking. WARNING: some files may get deleted",
    )

    args = parser.parse_args()
    ################ Creating all required directories ############################
    os.makedirs(EXTRACTED_TEXT_FOLDER, exist_ok=True)
    os.makedirs(TOKEN_COUNT_FOLDER, exist_ok=True)
    os.makedirs(NOTES_OUTPUT_FOLDER, exist_ok=True)
    os.makedirs(PDF_PAPERS_FOLDER, exist_ok=True)

    ################ Flattening PDFs directory ############################

    print(f"Flattening... {PDF_PAPERS_RAW_FOLDER} --> {PDF_PAPERS_FOLDER}")
    flatten_folder(PDF_PAPERS_RAW_FOLDER, PDF_PAPERS_FOLDER)
    print(f"Flattened successfully")

    ################ Reading Contents of Folders #############################

    existing_text_files = filenames_in_folder(EXTRACTED_TEXT_FOLDER, FileType.TXT)
    existing_token_files = filenames_in_folder(TOKEN_COUNT_FOLDER, FileType.TOKEN)
    pdf_files = filenames_in_folder(PDF_PAPERS_FOLDER, FileType.PDF)
    pdf_files_len = len(pdf_files)

    ################# Checking all reference keys exist #####################
    with open(JSON_REFERENCE_KEY_FILE) as f:
        reference_key_file: list[dict[str, str]] = json.load(f)
        reference_key_map = reference_key_map_generator(reference_key_file, pdf_files)

    no_reference_keys_for = set(pdf_files).difference(set(reference_key_map.keys()))
    if len(no_reference_keys_for) > 0:
        print(
            f"ERROR | Not found reference key for, make sure all reference pdf files have corresponding reference keys before continuing"
        )
        for n in no_reference_keys_for:
            print(f"- {n}")
        return

    ################ Removing unlinked TXT files #############################

    txt_files_with_no_matching_pdfs = set(existing_text_files).difference(
        set(reference_key_map.values())
    )

    if len(txt_files_with_no_matching_pdfs) > 0:
        for f in txt_files_with_no_matching_pdfs:
            print(f"WARNING | No matching PDF for existing txt file: {f}")

        if args.all or ask_user("Do you want to remove these files?"):
            for f in txt_files_with_no_matching_pdfs:
                path = os.path.join(EXTRACTED_TEXT_FOLDER, f + FileType.TXT.value)
                os.remove(path)
                print(f"Removed: {path}")

    ################ Extracting PDF to TXT ##################################

    if not (
        args.all
        or ask_user("Step 1: Now we will extract text from PDF files. Proceed?")
    ):
        return

    print("Initializing tokenizer")
    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_MODEL)

    for i, (pdf_filename, reference_key) in enumerate(reference_key_map.items()):
        it = i + 1

        if (
            reference_key in existing_text_files
            and reference_key in existing_token_files
        ):
            logProgress(
                it, pdf_files_len, f"Skipping already processed: {reference_key}"
            )
            continue

        text = convert_to_txt(pdf_filename)

        # Saving TXT
        txt_path = os.path.join(
            EXTRACTED_TEXT_FOLDER, reference_key + FileType.TXT.value
        )
        with open(txt_path, "w", encoding="utf-8") as txt_file:
            logProgress(
                it, pdf_files_len, f"Saved {reference_key}"
            )
            txt_file.write(text)

        token_count = len(tokenizer.encode(text, add_special_tokens=True))

        # Saving TOKEN
        file_path = os.path.join(
            TOKEN_COUNT_FOLDER, reference_key + FileType.TOKEN.value
        )
        with open(file_path, "w", encoding="utf-8") as json_file:
            json.dump({"tokens": token_count}, json_file, indent=4)

        logProgress(
            it, pdf_files_len, f"Processed {token_count} tokens: {reference_key}"
        )

    print("Extraction complete")

    ################ Checking TOKEN Warnings ##################################

    token_files = filenames_in_folder(TOKEN_COUNT_FOLDER, FileType.TOKEN)

    token_warnings = []
    for f in token_files:
        path = os.path.join(TOKEN_COUNT_FOLDER, f + FileType.TOKEN.value)
        with open(path, "r") as f:
            tokens = int(json.loads(f.read())["tokens"])
            if tokens > MAX_API_TOKENS_ALLOWED:
                token_warnings.append((f, tokens))
                print(f)
    if len(token_warnings) > 0:
        print()
        print(f"Following files exceed allowed token amount {MAX_API_TOKENS_ALLOWED}:")
        for file, tokens in token_warnings:
            print(f"- {tokens} | {file}")

        if args.all or ask_user("Do you want to remove these files?"):
            for file, _ in token_warnings:
                txt_path = os.path.join(
                    EXTRACTED_TEXT_FOLDER, file + FileType.TXT.value
                )
                pdf_path = os.path.join(PDF_PAPERS_FOLDER, file + FileType.PDF.value)
                token_path = os.path.join(
                    TOKEN_COUNT_FOLDER, file + FileType.TOKEN.value
                )
                for p in [txt_path, token_path, pdf_path]:
                    os.remove(p)
                    print(f"Removed: {p}")

    ################ Checking Redundant Notes ##############################

    notes_names = filenames_in_folder(NOTES_OUTPUT_FOLDER, FileType.FOLDER)
    redundant_notes = set(notes_names).difference(set(reference_key_map.values()))
    if len(redundant_notes) > 0:
        for f in redundant_notes:
            print(f"WARNING | Redundunt notes exist in folder: {f}")
        if args.all or ask_user("Do you want to remove these files?"):
            for f in redundant_notes:
                path = os.path.join(NOTES_OUTPUT_FOLDER, f)
                shutil.rmtree(path)
                print(f"Removed: {path}")

    ################ Generating Notes ##################################

    if not (
        args.all
        or ask_user(
            "Step 2: Now we will generate atomic notes out of extracted texts. Proceed?"
        )
    ):
        return

    asyncio.run(create_notes())


if __name__ == "__main__":
    main()
