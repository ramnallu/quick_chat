# Test the split_into_sections function
import sys
sys.path.append('scripts')

from ingest_documents import split_into_sections

# Read the file
with open('data/white tiger martial arts/white tiger martial arts.txt', 'r', encoding='utf-8') as f:
    content = f.read()

print(f'File content length: {len(content)}')
print('First 200 chars:')
print(repr(content[:200]))
print()

# Split into sections
sections = split_into_sections(content, 'data/white tiger martial arts/white tiger martial arts.txt')

print(f'Number of sections found: {len(sections)}')
for i, section in enumerate(sections):
    section_name = section["section"]
    text_len = len(section["text"])
    preview = section["text"][:100]
    print(f'Section {i+1}: {section_name} (length: {text_len})')
    print(f'  Preview: {preview}...')
    print()