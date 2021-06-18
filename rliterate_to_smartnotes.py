#!/usr/bin/env python3

import smartnotes

class RliterateToSmartNotesConverter(object):

    def convert(self, rliterate_path, smart_notes_path):
        self.note_db = smartnotes.NoteDb(smart_notes_path)
        rliterate = smartnotes.read_json_file(rliterate_path, {})
        self.variables = rliterate["variables"]
        self.convert_page(rliterate["root_page"])

    def convert_page(self, page, parent_page_note_id=None):
        page_note_id = self.note_db.create_note(**{
            "text": page["title"],
            "tags": ["title"],
        })
        if parent_page_note_id is not None:
            self.note_db.create_link(parent_page_note_id, page_note_id)
        for paragraph in page["paragraphs"]:
            if paragraph["type"] == "text":
                self.note_db.create_link(
                    page_note_id,
                    self.note_db.create_note(
                        text=self.convert_text_fragments(paragraph["fragments"])
                    )
                )
            elif paragraph["type"] == "code":
                self.note_db.create_link(
                    page_note_id,
                    self.note_db.create_note(**{
                        "type": "code",
                        "text": "<code>",
                        "filepath": paragraph["filepath"],
                        "chunkpath": paragraph["chunkpath"],
                        "fragments": self.convert_code_fragments(paragraph["fragments"]),
                    })
                )
            elif paragraph["type"] == "list":
                self.convert_list(paragraph, page_note_id)
            else:
                raise ValueError(f"Unknown paragraph type {paragraph['type']}")
        for child in page["children"]:
            self.convert_page(child, page_note_id)

    def convert_code_fragments(self, fragments):
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

    def convert_list(self, list, parent_note_id):
        if list["child_type"] is None and len(list["children"]) == 0:
            return
        list_note_id = self.note_db.create_note(
            text=f"<{list['child_type']} list>"
        )
        self.note_db.create_link(parent_note_id, list_note_id)
        for child in list["children"]:
            self.note_db.create_link(
                list_note_id,
                self.note_db.create_note(
                    text=self.convert_text_fragments(child["fragments"])
                )
            )
            self.convert_list(child, list_note_id)

    def convert_text_fragments(self, fragments):
        return "".join(
            fragment["text"] if fragment["text"] else fragment["page_id"]
            for fragment
            in fragments
        )

if __name__ == "__main__":
    RliterateToSmartNotesConverter().convert("smartnotes.rliterate", "smartnotes.notes")
