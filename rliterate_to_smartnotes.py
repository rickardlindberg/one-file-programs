#!/usr/bin/env python3

import smartnotes

class RliterateToSmartNotesConverter(object):

    def convert(self, rliterate_path, smart_notes_path):
        self.rliterate = smartnotes.read_json_file(rliterate_path, {})
        self.note_db = smartnotes.NoteDb(smart_notes_path)
        self.page_links = set()
        self.page_id_to_note_id = {}
        self.convert_page(self.rliterate["root_page"])
        for note_id, page_id in self.page_links:
            self.note_db.create_link(note_id, self.page_id_to_note_id[page_id])

    def convert_page(self, page, parent_page_note_id=None):
        page_note_id = self.note_db.create_note(**{
            "text": page["title"],
            "tags": ["title"],
        })
        self.page_id_to_note_id[page["id"]] = page_note_id
        if parent_page_note_id is not None:
            self.note_db.create_link(parent_page_note_id, page_note_id)
        for paragraph in page["paragraphs"]:
            if paragraph["type"] == "text":
                self.create_text_fragments_note(page_note_id, paragraph["fragments"])
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
                raise ValueError(f"Unknown paragraph {paragraph}")
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
                    text = self.rliterate["variables"][fragment["id"]]
                else:
                    text += self.rliterate["variables"][fragment["id"]]
            else:
                raise ValueError(f"Unknown code fragment {fragment}")
        if text is not None:
            x.extend({"type": "line", "text": x} for x in text.splitlines())
            text = None
        return x

    def convert_list(self, list_obj, parent_note_id):
        if list_obj["child_type"] is None and len(list_obj["children"]) == 0:
            return
        list_note_id = self.note_db.create_note(
            text=f"<{list_obj['child_type']} list>"
        )
        self.note_db.create_link(parent_note_id, list_note_id)
        for child in list_obj["children"]:
            self.create_text_fragments_note(list_note_id, child["fragments"])
            self.convert_list(child, list_note_id)

    def create_text_fragments_note(self, parent_note_id, fragments):
        self.text_fragments_page_links = set()
        child_note_id = self.note_db.create_note(
            text=self.convert_text_fragments(fragments)
        )
        self.note_db.create_link(parent_note_id, child_note_id)
        for page_id in self.text_fragments_page_links:
            self.page_links.add((child_note_id, page_id))

    def convert_text_fragments(self, fragments):
        return "".join(
            self.convert_text_fragment(fragment)
            for fragment
            in fragments
        )

    def convert_text_fragment(self, fragment):
        if fragment["type"] == "text":
            return fragment["text"]
        elif fragment["type"] == "code":
            return "`{}`".format(fragment["text"])
        elif fragment["type"] == "reference":
            self.text_fragments_page_links.add(fragment["page_id"])
            return self.get_page_title(fragment["page_id"], fragment["text"])
        else:
            raise ValueError(f"Unknown text fragment {fragment}")

    def get_page_title(self, page_id, default):
        if default:
            return default
        else:
            return self.find_page(page_id)["title"]

    def find_page(self, page_id, page=None):
        if page is None:
            page = self.rliterate["root_page"]
        if page["id"] == page_id:
            return page
        for child in page["children"]:
            page = self.find_page(page_id, child)
            if page is not None:
                return page

if __name__ == "__main__":
    RliterateToSmartNotesConverter().convert("smartnotes.rliterate", "smartnotes.notes")
