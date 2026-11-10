"""Synthetic, preset analysis: no model calls and no private paper inputs."""
import hashlib
from pathlib import Path
from reportlab.pdfgen import canvas
from paper_research_coach.paper_study import index_pdf, source_images, validate_analysis, render_study

root = Path(__file__).resolve().parent
path = root / 'synthetic-study.pdf'
c = canvas.Canvas(str(path), pagesize=(600, 800))
c.setFont('Helvetica-Bold', 16)
c.drawString(50, 748, 'Synthetic Budget-Matched Study')
c.setFont('Helvetica', 10)
c.drawString(50, 726, 'Synthetic teaching material. Preset analysis, not live model output.')
c.setFont('Helvetica-Bold', 13)
c.drawString(50, 680, '1 Introduction')
c.setFont('Helvetica', 12)
c.drawString(50, 650, 'We compare two algorithms under the same training budget.')
c.drawString(50, 628, 'The proposed rule chooses observations before updating the estimate.')
c.drawString(50, 606, 'A higher score alone does not establish generalization to new tasks.')
c.setFont('Helvetica-Bold', 13)
c.drawString(50, 554, '2 Evidence')
c.setFont('Helvetica', 12)
c.drawString(50, 524, 'Algorithm A scores 75 and algorithm B scores 70 in this synthetic example.')
c.drawString(50, 502, 'Both use ten updates. No uncertainty interval is available.')
c.setStrokeColorRGB(.2,.4,.6)
c.line(70, 320, 400, 320); c.line(70,320,70,460)
c.setFillColorRGB(.35,.55,.75); c.rect(140,320,70,120, fill=1); c.rect(280,320,70,112, fill=1)
c.setFillColorRGB(0,0,0); c.drawString(150,300,'A: 75'); c.drawString(290,300,'B: 70')
c.drawString(70,270,'Teaching illustration only; not a published experiment.')
c.save()
paper = {'id':'synthetic-demo', 'source_version':hashlib.sha256(path.read_bytes()).hexdigest(), 'source_path':str(path)}
paragraphs, unreadable = index_pdf(paper)
analyses = {}
for p in paragraphs:
    text = p['text']
    quote = next((q for q in ['We compare two algorithms under the same training budget.', 'Both use ten updates. No uncertainty interval is available.', '1 Introduction', '2 Evidence'] if q in text), text.splitlines()[0])
    analyses[p['id']] = validate_analysis({'translation':'【预设示范分析，非实时模型输出】这是一份合成教学材料。比较必须保持训练预算一致；例子里的分数差异不能单独证明新任务上的泛化能力。没有不确定性区间，需要继续核查。', 'function':'提出比较条件或提供合成例子。', 'role':'把主张连接到预算条件与证据边界。', 'critique':'只有一次合成比较，尚不足以判断统计稳定性或跨任务效果。', 'marks':[{'quote':quote,'category':'method' if 'budget' in quote else 'evidence'}], 'concepts':['训练预算：两方法投入的资源','泛化：未见任务上的表现'], 'steps':['选择观测','更新估计','在相同条件下比较'], 'claim':'同预算比较有助于排查资源投入差异，但不能独立证明泛化。'}, p)
first=paragraphs[0]
study = {'id':'study-demo','revision':1,'title':'合成论文研读示范｜预设分析，非实时模型输出','source_version':paper['source_version'],'scope':'full','paragraphs':paragraphs,'analyses':analyses,'unreadable_pages':unreadable,'page_images':source_images(paper,paragraphs),'summary':{'claim':'相同训练预算是公平比较的必要检查条件之一。','strongest':{'paragraph_id':first['id'],'quote':first['text'].splitlines()[0],'reason':'明确展示材料和分析的合成性质。'},'weakest':{'paragraph_id':paragraphs[-1]['id'],'quote':paragraphs[-1]['text'].splitlines()[0],'reason':'示范没有独立重复与不确定性估计，需要继续核查。'}},'summary_paragraphs':len(paragraphs)}
note={'id':'demo-user-note','author':'user','content':'【示范用户批注】我想进一步核查：如果两组预算不同，这个结论还成立吗？','anchor':{**first['anchor']}}
(root/'synthetic-study.html').write_text(render_study(study,[note]),encoding='utf-8')
print(root/'synthetic-study.html')
