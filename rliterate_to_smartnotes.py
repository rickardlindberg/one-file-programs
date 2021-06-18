#!/usr/bin/env python3

import smartnotes

class RliterateToSmartNotesConverter(object):

    def convert(self, rliterate_path, smart_notes_path):
        self.note_db = smartnotes.NoteDb(smart_notes_path)
        rliterate = smartnotes.read_json_file(rliterate_path, {})
        self.variables = rliterate["variables"]
        self.write_page(rliterate["root_page"])

    def write_page(self, page, parent=None):
        page_id = self.note_db.create_note(**{
            "text": page["title"],
            "tags": ["title"],
        })
        if parent is not None:
            self.note_db.create_link(parent, page_id)
        for paragraph in page["paragraphs"]:
            if paragraph["type"] == "text":
                self.note_db.create_link(
                    page_id,
                    self.note_db.create_note(
                        text=self.fragments_to_text(paragraph["fragments"])
                    )
                )
            elif paragraph["type"] == "code":
                self.note_db.create_link(
                    page_id,
                    self.note_db.create_note(**{
                        "type": "code",
                        "text": "<code>",
                        "filepath": paragraph["filepath"],
                        "chunkpath": paragraph["chunkpath"],
                        "fragments": self.transform_code_fragments(paragraph["fragments"]),
                    })
                )
            elif paragraph["type"] == "list":
                self.note_db.create_link(
                    page_id,
                    self.note_db.create_note(text=self.list_to_text(paragraph))
                )
            else:
                raise ValueError(f"Unknown paragraph type {paragraph['type']}")
        for child in page["children"]:
            self.write_page(child, page_id)

    def transform_code_fragments(self, fragments):
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
                    text = self.variables[fragment["id"]]
                else:
                    text += self.variables[fragment["id"]]
            else:
                raise ValueError(f"Unknown code fragment type {fragment['type']}")
        if text is not None:
            x.extend({"type": "line", "text": x} for x in text.splitlines())
            text = None
        return x

    def list_to_text(self, list):
        if list["child_type"] == "unordered":
            return "".join(
                "* {}\n".format(self.list_to_text(child))
                for child in list["children"]
            )
        elif list["child_type"] is None:
            self.fragments_to_text(list["fragments"])
        else:
            raise ValueError(f"Unknown child_type {list['child_type']}")

    def fragments_to_text(self, fragments):
        return "".join(
            fragment["text"] if fragment["text"] else fragment["page_id"]
            for fragment
            in fragments
        )

if __name__ == "__main__":
    RliterateToSmartNotesConverter().convert("smartnotes.rliterate", "smartnotes.notes")
