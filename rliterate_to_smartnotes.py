#!/usr/bin/env python3

import smartnotes

def rliterate_to_smartnotes(rliterate_path, smart_notes_path):
    note_db = smartnotes.NoteDb(smart_notes_path)
    rliterate = smartnotes.read_json_file(rliterate_path, {})
    write_page(rliterate["root_page"], note_db, rliterate["variables"])

def write_page(page, note_db, variables, parent=None):
    page_id = note_db.create_note(**{
        "text": page["title"],
        "tags": ["title"],
    })
    if parent is not None:
        note_db.create_link(parent, page_id)
    for paragraph in page["paragraphs"]:
        if paragraph["type"] == "text":
            note_db.create_link(
                page_id,
                note_db.create_note(
                    text=fragments_to_text(paragraph["fragments"])
                )
            )
        elif paragraph["type"] == "code":
            note_db.create_link(
                page_id,
                note_db.create_note(**{
                    "type": "code",
                    "text": "<code>",
                    "filepath": paragraph["filepath"],
                    "chunkpath": paragraph["chunkpath"],
                    "fragments": transform_code_fragments(paragraph["fragments"], variables),
                })
            )
        elif paragraph["type"] == "list":
            note_db.create_link(
                page_id,
                note_db.create_note(text=list_to_text(paragraph))
            )
        else:
            raise ValueError(f"Unknown paragraph type {paragraph['type']}")
    for child in page["children"]:
        write_page(child, note_db, variables, page_id)

def transform_code_fragments(fragments, variables):
    x = []
    text = None
    for fragment in fragments:
        if fragment["type"] == "chunk":
            if text is not None:
                x.extend({"type": "line", "text": x} for x in text.splitlines())
                text = None
            x.append(fragment)
        elif fragment["type"] == "code":
            if text is None:
                text = fragment["text"]
            else:
                text += fragment["text"]
        elif fragment["type"] == "variable":
            if text is None:
                text = variables[fragment["id"]]
            else:
                text += variables[fragment["id"]]
        else:
            raise ValueError(f"Unknown code fragment type {fragment['type']}")
    if text is not None:
        x.extend({"type": "line", "text": x} for x in text.splitlines())
        text = None
    return x

def list_to_text(list):
    if list["child_type"] == "unordered":
        return "".join(
            "* {}\n".format(list_to_text(child))
            for child in list["children"]
        )
    elif list["child_type"] is None:
        fragments_to_text(list["fragments"])
    else:
        raise ValueError(f"Unknown child_type {list['child_type']}")

def fragments_to_text(fragments):
    return "".join(
        fragment["text"] if fragment["text"] else fragment["page_id"]
        for fragment
        in fragments
    )

if __name__ == "__main__":
    rliterate_to_smartnotes("smartnotes.rliterate", "smartnotes.notes")
