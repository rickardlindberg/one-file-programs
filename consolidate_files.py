#!/usr/bin/env python3

from collections import defaultdict
import difflib
import os
import smartnotes

def consolidate_files(path):
    db = smartnotes.NoteDb(path)
    parts = collect_parts(db)
    for (file, chunk) in parts.keys():
        if file != tuple() and chunk == tuple():
            consolidate(os.path.join(*file), file, chunk, parts, db)
    parts = collect_parts(db)
    for (file, chunk) in parts.keys():
        if file != tuple() and chunk == tuple():
            path = os.path.join(*file)
            with open(path) as f:
                file_on_disk = f.read()
            file_in_memory = collect(file, chunk, parts)
            if file_on_disk != file_in_memory:
                print(f"Consolidation failure for: {path}")
                with open(f"{path}.consolidated", "w") as f:
                    f.write(file_in_memory)

def collect_parts(db):
    parts = defaultdict(list)
    for note_id, note in reversed(db.get_notes()):
        if note.get("type", None) == "code":
            key = (tuple(note["filepath"]), tuple(note["chunkpath"]))
            parts[key].append((note_id, note["fragments"]))
    return parts

def consolidate(path, file, chunk, parts, db):
    old_lines = []
    collect_lines(old_lines, file, chunk, parts)
    with open(path) as f:
        new_lines = f.read().splitlines()
    sm = difflib.SequenceMatcher(a=[x[1] for x in old_lines], b=new_lines)
    note_actions = defaultdict(list)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        print((tag, i1, i2, j1, j2))
        if tag == "replace":
            first = None
            for tag, line in old_lines[i1:i2]:
                if tag is not None:
                    note_id, prefix, fragment_index = tag
                    if first is None:
                        first = tag
                    note_actions[note_id].append(('remove', fragment_index))
            if first:
                note_actions[first[0]].append((
                    'extend',
                    first[2],
                    [strip_prefix(first[1], x) for x in new_lines[j1:j2]]
                ))
        elif tag == "delete":
            for tag, line in old_lines[i1:i2]:
                if tag is not None:
                    note_id, prefix, fragment_index = tag
                    note_actions[note_id].append(('remove', fragment_index))
        elif tag == "insert":
            index = i1
            while True:
                tag, line = old_lines[index]
                if tag:
                    note_id, prefix, fragment_index = tag
                    note_actions[note_id].append((
                        'extend',
                        fragment_index,
                        [strip_prefix(prefix, x) for x in new_lines[j1:j2]]
                    ))
                    break
                else:
                    index += 1
        elif tag == "equal":
            # Nothing to do
            pass
        else:
            raise ValueError(f"Unknown op_code tag {tag}")
    for note_id, actions in note_actions.items():
        note = db.get_note_data(note_id)
        db.update_note(
            note_id,
            fragments=consolidate_fragments(note["fragments"], actions)
        )

def strip_prefix(prefix, line):
    if line.startswith(prefix):
        return line[len(prefix):]
    else:
        return line

def consolidate_fragments(fragments, actions):
    print(actions)
    removes = set()
    extends = {}
    for action in actions:
        if action[0] == 'remove':
            removes.add(action[1])
        elif action[0] == 'extend':
            extends[action[1]] = action[2]
        else:
            raise ValueError(f"Unknown action {action}")
    new_fragments = []
    for index, fragment in enumerate(fragments):
        if index in extends:
            for line in extends[index]:
                new_fragments.append({"type": "line", "text": line})
        if index not in removes:
            new_fragments.append(fragment)
    return new_fragments

def collect(file, chunk, parts):
    lines = []
    collect_lines(lines, file, chunk, parts)
    return "\n".join(line[1] for line in lines) + "\n"

def collect_lines(lines, file, chunk, parts, prefix="", blank_lines_before=0):
    for index, (note_id, fragments) in enumerate(parts.get((file, chunk), [])):
        if index > 0:
            for foo in range(blank_lines_before):
                lines.append((None, ""))
        for fragment_index, fragment in enumerate(fragments):
            if fragment["type"] == "line":
                if fragment["text"]:
                    lines.append(((note_id, prefix, fragment_index), prefix+fragment["text"]))
                else:
                    lines.append(((note_id, prefix, fragment_index), ""))
            elif fragment["type"] == "chunk":
                collect_lines(
                    lines,
                    file,
                    tuple(list(chunk)+fragment["path"]),
                    parts,
                    prefix=prefix+fragment["prefix"],
                    blank_lines_before=fragment["blank_lines_before"],
                )
            else:
                raise ValueError(f"Unknown code fragment type {fragment['type']}")

if __name__ == "__main__":
    consolidate_files("smartnotes.notes")
