# The reading method: why read papers this way

[简体中文](METHOD.md) · [Design](DESIGN.md) · [Sources and evidence levels](SOURCES.md)

This page answers four questions: **where** the method comes from, **what** it distils into, **why** each practice is there, and **what it can and cannot do for you**.

> In one sentence: the goal of reading a paper is not to finish it or understand every sentence, but to be able to say **what judgment this paper changes, why I believe it, and how it changes my next research step.** Everything below serves those three sentences.

---

## 1. The problem we start from

Many graduate students know the feeling: you read a paper end to end, understand every sentence, close the PDF and cannot say what the authors actually found. You highlighted half a page and wrote a tidy summary, yet one question in group meeting — “could the gain just come from a bigger compute budget?” — leaves you stuck.

That is less about effort than about method. Learning research is fairly consistent here:

- **Rereading, highlighting and summarising are low-utility strategies.** Dunlosky et al. (2013) reviewed ten common techniques and rated these three low; practice testing (active recall) and distributed practice rated high. The habits students use most are among the weakest.
- **Familiarity masquerades as understanding.** Koriat and Bjork call this an illusion of competence: with the material in front of you, you overestimate what you could do without it. Rozenblit and Keil’s illusion of explanatory depth shows that what people believe they understand often collapses when they must explain the mechanism step by step.
- **AI help can deepen the illusion.** In a randomised experiment, Bastani et al. (PNAS 2025) found that better performance *with* AI did not mean more learning once AI was removed, and unguarded answer-giving could even hurt later independent performance. A fluent AI summary reads well, but fluency is not judgment.

So this project deliberately does **not** build a better AI summary. It spends its effort on getting you to predict, check, explain and recall.

## 2. Where the method comes from

Sources fall into three layers, kept apart by what each can support (full verification scope in [SOURCES.md](SOURCES.md)):

| Layer | Representative sources | What it contributes |
|---|---|---|
| **Researchers’ experience** | Harry Shum and Gang Hua, “three levels, four stages and ten questions for reading research papers” (MSRA); Shuyi Wang, “How to read papers efficiently” (relaying Peter W. Carr’s reading tutorial); S. Keshav, *How to Read a Paper*; Michael Nielsen, *Principles of Effective Research*; Richard Hamming, “You and Your Research”; Uri Alon, *How to Choose a Good Scientific Problem*; Mu Li’s paper-reading talks; Research-Starter-Kit; Sida Peng’s learning_research; Miriam Sweeney, *How to Read for Grad School* | How experienced researchers **budget reading effort**, **find the contribution**, and **turn reading into their own questions** |
| **Scientific method** | John Platt, *Strong Inference* (1964); T. C. Chamberlin, *The Method of Multiple Working Hypotheses* (1890); Popper’s falsifiability; Toulmin’s model of argument | How to **interrogate a claim**: list alternative explanations and find a test that discriminates between them |
| **Learning science and teaching research** | Cognitive apprenticeship (Collins, Brown & Holum); scaffolding (Wood, Bruner & Ross); cognitive load and the expertise reversal effect (Sweller; Kalyuga et al.); retrieval practice (Roediger & Karpicke; Karpicke & Blunt); the generation effect and the value of failed attempts (Slamecka & Graf; Kornell, Hays & Bjork); self-explanation (Chi et al.); the ICAP framework (Chi & Wylie); distributed practice (Cepeda et al.); the CREATE and QALMRI approaches to primary literature | **Why** these practices tend to leave more transferable understanding than passive reading, and **how much** an AI should help |

> [!IMPORTANT]
> These sources support **design motivation**, not a claim that this tool works. Experience is not an experiment, and most learning-science studies used other learners and materials; they do not transfer automatically to PhD students reading frontier papers. There is **no** human learning-outcome trial for this project yet; see the [trial protocol](HUMAN-TRIAL.md).

## 3. What reading actually is: from passive to creative

Steven Pinker (*The Sense of Style*) describes writing as turning a **web** of ideas into a **tree** of syntax and then a **string** of words. Harry Shum compares a paper to Shannon’s channel — writing encodes, reading decodes — but real reading goes further: you repeatedly infer the author’s intent, break it into pieces you can explain, and build them into your own **cognitive model**. So:

- The aim is to **rebuild the author’s web** and work on it, not to memorise the string — which is why you need not read word by word from the start.
- **Deep reading gives deep understanding; shallow reading gives shallow understanding.** Depth should follow purpose.

Shum names four stages of reading, which is also where this method tries to take you:

| Stage | What you do | How the method pushes you up one level |
|---|---|---|
| **Passive** | Roughly know what it says | State the problem, inputs and outputs in one sentence |
| **Active** | Ask what the knowledge is good for | Relate it to your own task |
| **Critical** | Read assuming “there may be a flaw; find it” | One critical question at a time: right problem? a simpler solution not considered? enough data, read reasonably? |
| **Creative** | Work out what you can do with it | What is the good idea? What did the authors miss? What could I do now? |

**Reading an AI summary mostly stays at stage one.** Gang Hua argues that rigorous training can take you to critical reading, while creative reading needs your own background turned into your own “story” — no template guarantees it, but pushing up one level each time you read trains it. The seven principles below are how.

## 4. Seven principles: what, why, and where in the tool

### 1. Read with a purpose and invest in layers

**Practice.** Before reading, name the judgment you need — a map of the field, whether a method transfers to your system, a group-meeting talk — and pick a depth: *skim* (decide whether to continue), *understand* (explain contribution and evidence), *reconstruct* (rebuild the reasoning or a minimal implementation and find its limits). Stopping after a few minutes because the paper does not serve your question **is a valid outcome**.

**Don’t read linearly.** Without a clear entry point, follow Professor Peter W. Carr’s order (as relayed by Shuyi Wang):

1. **Title, keywords, abstract** → continue?
2. **Conclusion** → is this research I care about?
3. **Figures and tables only**, without the surrounding text → they show most honestly where the paper actually went and how far;
4. **Introduction** → often sells significance; read it with the figures in mind;
5. **Results and discussion** → what the authors dug out of the results; this is where skill shows;
6. **Methods and experimental details** → hardest and slowest; read them slowly, even try to reproduce, only if the earlier steps say it is worth it.

You may **stop after any step, or drop the paper** — don’t chase sunk costs. This matches Shum’s three levels: **skim** (quickly know what it says), **careful reading** (critical and creative), **study** (implement the algorithm yourself).

**Why.** Keshav’s three-pass method is really about **layered investment**: a few minutes decide whether a paper deserves more, and most papers rightly stop there. Adler and Van Doren’s distinction between inspectional and analytical reading makes the same point. Sweeney frames graduate reading as purpose-driven rather than volume-driven; Alon and Hamming remind us that time is a researcher’s scarcest resource, so what to read is itself a research decision.

Choosing papers works the same way: aim high. Faced with a pile of search results, a beginner can order them by how reliable the venue is — recognised top journals and conferences and peer-reviewed papers first, theses (especially undergraduate theses) later (Shuyi Wang). It is a prior on what to read first, not a hard threshold, and it never replaces checking the actual evidence.

**In the tool.** The route opens with a reading goal; depth and stage are tracked separately; screening a paper out saves a reason and a restart condition instead of faking 8/8.

### 2. Find what changed before filling in background

**Practice.** Give just enough background to make the problem intelligible, then write a **provisional contribution sentence**:

> The closest prior route is limited by Y under condition X; this paper’s key change is Z; evidence E supports it up to boundary B.

Leave the gaps empty and revise the sentence as you read.

Read the introduction through Jim Kajiya’s five questions, which Shum recommends — one sentence each: **what it is about · what problem it solves · why the problem is interesting · what is really new (and what isn’t) · why it is neat**. For Shum, *what’s new* is the ultimate question of research. An empty box is the next piece of evidence to look for.

**Why.** Mu Li’s paper readings repeatedly start from title, abstract, conclusion and key figures to grasp what problem is solved and what was achieved before deciding to go deep. Keshav’s first pass answers the “five Cs”, contribution among them. Research-Starter-Kit asks first for the naïve solution and why the paper needs more. A provisional judgment acts as an **organising frame**: each later detail has somewhere to attach, instead of becoming one more line in an evenly weighted summary.

We avoid a full background tour, which loses the question, and we avoid jumping to an “insight” slogan, which flattens the paper. Also, **the order of the argument is not the order of discovery**: without the authors’ own account, the coach says “one way to understand this design is…”, never invents a eureka story.

**In the tool.** Step 2 compares against the closest prior work; observation, mechanism and benefit are verified separately.

### 3. Predict before you look at the evidence

**Practice.** At a pivotal claim, state two plausible explanations, then ask: *which observation would tell them apart, and what do you expect to see?* Only then open the real figure or proof. Being wrong is fine; the gap between prediction and observation is where learning happens.

**Why.**

- **Scientific method.** Platt’s strong inference asks for several alternative hypotheses and a crucial experiment that excludes some of them; Chamberlin warned against falling in love with a single explanation. Reading a paper this way treats the authors’ experiment as that crucial test.
- **Learning science.** The generation effect shows that self-generated answers are remembered better than read ones; Kornell, Hays and Bjork found that even an **unsuccessful** attempt before seeing the answer improves later learning — one of Bjork’s “desirable difficulties”.
- **Teaching research.** CREATE has students map concepts, predict results and design follow-up experiments while reading primary papers; QALMRI breaks a study into Question, Alternatives, Logic, Method, Results and Inferences. Both put the reader in the researcher’s seat before the conclusion.

**Limits.** Not every turn is a quiz. For definitions, missing background, an explicit request for the answer, or fatigue, a direct explanation fits better, and you are never asked to guess facts you clearly lack.

**In the tool.** The “challenge my judgment” help mode and the predict → look → compare flow; restating after seeing the answer is recorded as a restatement, not a prediction.

### 4. Look for alternative explanations and strong simple baselines

**Practice.** For the key claim ask: how far does a strong simple method get? Is there a more mundane explanation — more training budget, extra information, leakage, sample selection, metric choice, implementation detail? Where does the support end — correlation is not causation, a mean gain is not a tail gain, one dataset is not a law, no significant difference is not equivalence.

Michael Mitzenmacher’s *How to Read a Research Paper*, quoted by Shum, phrases critical reading as three groups of questions; ask the most relevant one:
- If the authors solve a problem: is it the **right problem**? Are there **simple solutions they did not consider**? What are the **limitations**?
- If they present data: is it the **right data** for the argument? **Gathered correctly**? **Interpreted reasonably**? Are there **more compelling datasets**?
- Assumptions and logic: is the logic sound given the assumptions? Is there a **flaw in the reasoning**?

**Why.** Popper: a claim is worth what could refute it. Toulmin splits an argument into claim, grounds, warrant, qualifier and rebuttal — exactly the distance between “the authors claim” and “the evidence establishes”. QALMRI reserves the A for alternatives. Research-Starter-Kit and Nielsen both stress naïve solutions and strong baselines, which are both a yardstick for the paper and your cheapest starting point for future work.

**In the tool.** One pivotal claim at a time; checks adapted to the paper type — see [paper-types.md](../skills/paper-research-coach/references/paper-types.md).

### 5. One move per turn; help fades by ability

**Practice.** Each turn advances one cognitive move: a real location, the explanation needed, at most one thinking task. Help has four levels — **model → guided → prompt-only → independent** — tracked **per ability**: you may explain mechanisms independently yet still need a worked example for statistical evidence.

**Why.** Cognitive load theory (Sweller): working memory is limited, and a page of summary plus five questions crowds out thinking. Scaffolding and cognitive apprenticeship (Wood, Bruner & Ross; Collins, Brown & Holum): expert skill is taught by modelling, coaching and fading support while making tacit thinking **visible** — and research judgment is precisely what a finished paper hides. The expertise reversal effect (Kalyuga et al.): guidance that helps novices burdens experts, so help must follow actual performance. ICAP (Chi & Wylie): engagement rises from passive through active and constructive to interactive; reading an AI summary is passive, explaining and debating is constructive and interactive.

**When stuck.** Shum’s path, from cheap to expensive: look up terms → read references and reread → keep reading for the basic idea → ask “**what question were the authors trying to answer?**” → ask someone who knows → don’t get overwhelmed. Shuyi Wang adds: **note unfamiliar concepts and resolve them later**, or you break the flow of reading. The coach therefore asks whether a gap blocks the current judgment: if so, it isolates it with a minimal example; if not, it parks it to look up after the passage.

**In the tool.** There is no help setting: say “just a hint”, “explain directly” or “challenge me” in your message and the coach follows it for that turn, defaulting to the least help needed. These choices are not ability ratings; ability records need your actual answer — clicks, read explanations and “got it” are not evidence.

### 6. Keep your own words, not a polished summary

**Practice.** Your thoughts — rough, hesitant, later proved wrong — are saved verbatim, separate from AI comments, anchored back to the PDF.

**Why.** Chi et al. showed that prompting learners to **self-explain** improves understanding; an AI-written summary removes exactly that process. And research ideas often originate in early misreadings and corrections: keep only the “correct summary” and you misjudge what you understood, and lose the hunch that first made you suspicious. Nielsen’s emphasis on continual reflection and record-keeping preserves that trail.

Carr sets a high bar for notes: **later, the notes alone should be enough — no second reading of the paper**. Such notes hold the problem, contribution, key evidence and its location, boundaries and your judgment, not a section-by-section abridgement, and they link to earlier notes and related papers. Shum suggests writing a **half-page review** of a good paper, ideally followed by a short talk: only by writing or saying it do you find what you missed.

**In the tool.** Exact words saved; “source marks” (the paper’s words) kept apart from “my thoughts”; the AI can only add linked comments; anchors are marked stale after a PDF version change.

### 7. End by recalling, and by a next step

**Practice.** A reading round ends not at the last page but when you (1) **recall once with the material closed** — explain the mechanism, predict a changed condition, state the evidence boundary — and (2) **leave a falsifiable next step**: under condition C, does mechanism M change outcome Y through variable V? What is the cheapest test, and what result would make you drop the idea?

**Why.** Retrieval practice (Roediger & Karpicke 2006; Karpicke & Blunt 2011) beats rereading and even concept mapping for long-term retention and understanding; distributed practice (Cepeda et al.’s meta-analysis) shows spacing helps further. Creative reading, in Shum’s words: once you know the author’s idea, ask what they did not think of, how to improve it, and what new thing you could do if you started this research now; connect it with other papers until an idea could carry three to five months of work. Gang Hua’s tenth question — **what can and should be done next** — decides whether you grow from student into independent researcher. Hamming: important research starts from important problems; Alon: choose problems by feasibility and interest; Nielsen: minimal tests and timely stopping; Martin Schwartz’s “The importance of stupidity in scientific research”: feeling lost in the unknown is the normal state of research — so “this direction is not worth pursuing” is a valuable conclusion too. Presenting to a specific audience is a test of whether the causal chain truly connects.

**In the tool.** Step 8 needs a real answer from this round; research-question cards hold the observation, hypothesis, alternative, strong simple baseline, minimal test and refutation condition. The default 1/3/7/14-day review spacing is an adjustable starting point, **not** a schedule proven optimal.

## 5. What it distils into

### The eight-step route: an evidence map, not a syllabus

| Step | Judgment to form | Main principles |
|---|---|---|
| 1. Reading goal | What do I need to decide, and how deep? | 1 |
| 2. Distinctive contribution | What changed relative to the closest prior work? | 2 |
| 3. Problem setting | Inputs, outputs, available information, assumptions, cost? | 2, 4 |
| 4. Mechanism | How does the key design overcome the difficulty? | 5 |
| 5. Evidence | Are baselines fair? Are alternatives excluded? | 3, 4 |
| 6. Boundaries | Under what conditions does the conclusion fail? | 4 |
| 7. Research implications | What is worth testing — or why stop? | 7 |
| 8. Recall and review | What can I recall unaided, and what next? | 7 |

The route defines what “fully read” means; it is not a gate in front of explanations. You can ask about any figure, equation or limitation at any time, and the return point stays where it was. See [reading-flow.md](../skills/paper-research-coach/references/reading-flow.md).

### Gang Hua’s ten questions: a coverage check

Hua calls this “template reading”: information passes through the bottleneck of ten questions so that only what matters enters your cognitive model. The eight steps and the ten questions cover each other:

| # | Question | Step |
|---|---|---|
| 1 | What problem does the paper address? What are the inputs and outputs? | Reading goal, problem setting |
| 2 | Is it a new problem? If not, why does it still matter? | Contribution |
| 3 | What hypothesis does it set out to prove? | Contribution, problem setting |
| 4 | What related work exists, and who are the key people? | Contribution (closest prior work) |
| 5 | What is the core contribution of the solution? | Mechanism |
| 6 | How are experiments designed to support each hypothesis? | Evidence |
| 7 | Which datasets? Are they available and reproducible? | Evidence |
| 8 | Do the results strongly support the hypothesis? | Evidence, boundaries |
| 9 | What is the contribution, **in your own words**? | Boundaries, recall |
| 10 | What can — and should — be done next? | Research implications |

Questions 9 and 10 are answered by you first and checked by the coach; an AI-written answer does not mean you have read the paper.

### Pocket tools

- **Five introduction questions** (Kajiya): about · problem · interesting · new · neat.
- **Three questions**: what judgment does this change; why do I believe it; how does it change my next step?
- **Contribution sentence**: the closest route is limited by Y under X; the key change is Z; evidence E supports it up to B.
- **Three-sentence verdict** (instead of “three pros, three cons”): what changed; the strongest evidence and its reach; what result would change my mind.
- **Research-question card**: observation and source / hypothesis / alternative / strong simple baseline / minimal test / refutation condition / next search question.
- **Non-native reading**: first tell a language gap from a concept or reasoning gap; keep qualifiers such as *may, under, assume, on average, compared with* — a smooth translation does not verify the claim.

## 6. What it helps you do

| Situation | What changes |
|---|---|
| Two hours in and still in the introduction | Abstract, conclusion and figures first; minutes to decide; method details last |
| Can’t say what the paper did | Each paper leaves a testable contribution sentence, not an evenly weighted summary |
| Stumped in group meeting | You already asked “what is the alternative explanation, is the baseline fair?” while reading |
| Many papers read, no ideas | Enter through a failure, contradiction, mechanism, missing information or cost, and land on a falsifiable question and minimal test |
| Thoughts vanish | Your words are saved with an anchor; you resume at the same passage |
| A week per paper | Minutes to decide whether a paper deserves more; a recorded stop is an outcome |
| Language and concepts tangled | Language and concept gaps are separated; no whole-paper translation needed |
| Worried AI will think for you | The AI defaults to locations and hints and fades help with your real performance; ask for a direct answer any time, but the judgment stays yours |

The long-term aim is a **transferable skill**: given any new paper, locate the contribution, find the decisive evidence, raise the strongest alternative, and decide what it means for your research. Paper counts and summary length are poor measures of that.

## 7. What it does not promise

- **No human learning-outcome trial yet.** Software tests check verbatim notes, versions and anchors, not whether your research ability improved.
- **Advice from experience is not experimental evidence.** We adopt ideas from Keshav, Mu Li and Nielsen without presenting them as proven.
- **Learning-science results do not transfer automatically.** Most studies involve school or undergraduate learners and shorter materials.
- **The AI can be wrong**, which is why explanations point back to the source for you to check.

## 8. Advice deliberately not adopted

Popular rules such as a fixed weekly paper quota, fixed time ratios, hard thresholds on venue or citation counts, mandatory three-pros-three-cons, or mechanically combining method A with method B into an idea are not enforced. They can help in context, but as rules they make volume look like judgment.

## 9. Further reading

1. **Harry Shum & Gang Hua — three levels, four stages and ten questions** (MSRA, in Chinese): the source of the four stages, the critical and creative questions and the ten-question template.
2. **Shuyi Wang — How to read papers efficiently** (in Chinese): selection, order and notes, with a summary of Peter W. Carr’s tutorial.
3. **S. Keshav — How to Read a Paper** (three pages): the most compact statement of layered investment.
4. **Mu Li — paper-reading video series** (in Chinese): a researcher grasping contributions and questioning experiments in real time.
5. **Brown, Roediger & McDaniel — Make It Stick**: retrieval practice, desirable difficulties and illusions of competence for a general audience.
6. **Michael Mitzenmacher — How to Read a Research Paper**: the original critical-reading checklist.
7. **Jim Kajiya — How to Get Your SIGGRAPH Paper Rejected**: what a paper’s opening must say, read in reverse as five introduction questions.
8. **John Platt — Strong Inference** (Science, 1964): thinking with alternative hypotheses and crucial experiments, equally useful when reviewing others’ experiments.
9. **Richard Hamming — You and Your Research** (talk; expanded in *The Art of Doing Science and Engineering*).
10. **Michael Nielsen — Principles of Effective Research**.
11. **Uri Alon — How to Choose a Good Scientific Problem** (Molecular Cell, 2009).
12. **Adler & Van Doren — How to Read a Book**.
13. **Booth, Colomb & Williams — The Craft of Research**.
14. **Charles Ling & Qiang Yang — Crafting Your Research Future** (Chinese edition 《学术研究，你的成功之道》; bibliographic details verified only).

Full citations and access scope: [SOURCES.md](SOURCES.md). If a principle does not fit your field, please [send a reading-improvement report](https://github.com/ooooooomygosh/paper-research-coach/issues/new/choose).
