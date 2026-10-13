# Answer me with HTML: what we adapted

The branch explainer reuses ideas and rules from **Answer me with HTML** (https://github.com/QingYunA/answer-me-with-html), which is MIT licensed:

- the Markdown draft syntax (front matter, `##` panels, and the `flow`, `sequence`, `tree`, `timeline`, `callout`, `ask` and `kv` fenced components), reduced to what a reading branch needs;
- the plain-writing check: sentence and paragraph limits, the English non-approved-word list, English passive voice, and the Chinese light-verb, cliché and vague-quantity rules (`src/paper_research_coach/explainer.py`).

We wrote our own parser (Python, returning typed JSON) and our own renderer (React). We do not bundle their CLI. A draft written for that project works here for these components. Their Chinese word list in turn comes from Simplified Technical Chinese (https://github.com/mzopedia/simplified-technical-chinese). Flow layout uses dagre (MIT).

The writing rules adapt the ideas of ASD-STE100 controlled writing. This is not an implementation or certification of ASD-STE100.

## License of the adapted material

MIT License

Copyright (c) 2026 Answer me with HTML contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
