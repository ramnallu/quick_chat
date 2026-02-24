#!/usr/bin/env python
"""Quick test to verify ResponseGenerator works correctly"""

from app.api import process_query
from datetime import datetime

print(f'Current Date: {datetime.now().strftime("%A, %B %d, %Y")}')
print()

# Test Suite
test_queries = [
    ('Is there a class today?', 'Date-aware query'),
    ('What programs do you offer?', 'Programs inquiry'),
    ('What is the white belt schedule?', 'Belt-specific schedule'),
    ('When are teen and adult classes?', 'Program schedule inquiry'),
    ('What are your hours?', 'Business hours inquiry'),
]

for query, test_type in test_queries:
    print(f'[{test_type}] {query}')
    print('-' * 70)
    try:
        result = process_query('white_tiger_martial_arts', query)
        answer = result['answer']
        # Truncate long answers for display
        if len(answer) > 200:
            print(answer[:200] + '...')
        else:
            print(answer)
    except Exception as e:
        print(f'ERROR: {e}')
    print()
