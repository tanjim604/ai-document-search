"""
Create the sample document library in sample_files/library/ (about 50 files).

    python scripts/generate_samples.py

The files cover many topics and every supported type, and include one exact
duplicate and one near duplicate, so search, summaries and similarity labels can
be tried on a realistic collection. Re-running overwrites the same files.
"""
import csv
import shutil
from pathlib import Path

import pymupdf
from docx import Document
from openpyxl import Workbook
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "sample_files" / "library"

# --------------------------------------------------------------------------- text documents
# (filename, title, paragraphs)
PDFS = [
    ("quantum-computing-primer.pdf", "A Primer on Quantum Computing", [
        "Quantum computers use qubits, which can exist in a superposition of zero and one. Unlike classical bits, a register of qubits can represent many states at once, and quantum algorithms use interference to amplify correct answers.",
        "Entanglement links qubits so that the state of one depends on the state of another. Shor's algorithm uses these effects to factor large numbers, which threatens many public-key encryption schemes used on the internet today.",
        "Current machines are noisy and have only hundreds of qubits. Error correction needs thousands of physical qubits for each reliable logical qubit, so practical, fault-tolerant quantum computing is still years away."]),
    ("climate-change-impacts.pdf", "Climate Change Impacts on Coastal Cities", [
        "Global temperatures have risen about 1.2 degrees Celsius since the industrial era, mainly because of greenhouse gas emissions from burning coal, oil and gas. Warmer oceans expand and glaciers melt, raising sea levels.",
        "Coastal cities face more frequent flooding, stronger storm surges and salt water entering fresh water supplies. Low-lying cities such as Miami, Jakarta and Dhaka are especially exposed.",
        "Adaptation measures include sea walls, restored wetlands, elevated buildings and managed retreat from the most vulnerable areas, alongside rapid cuts to emissions."]),
    ("transformer-architecture-explained.pdf", "The Transformer Architecture Explained", [
        "The transformer, introduced in 2017, replaced recurrent networks in natural language processing. Its key idea is self-attention, which lets every word in a sentence weigh its relationship to every other word in parallel.",
        "A transformer stacks layers of multi-head attention and feed-forward networks, with positional encodings that tell the model the order of tokens. Training in parallel made it practical to scale to billions of parameters.",
        "Large language models such as GPT and BERT are built on this architecture. They are pre-trained on huge text collections and then fine-tuned for tasks like translation, summarization and question answering."]),
    ("renewable-energy-report.pdf", "Renewable Energy Annual Report", [
        "Solar and wind power supplied more than a quarter of the world's electricity last year. The cost of solar panels has fallen by roughly ninety percent in a decade, making them the cheapest new source of power in most countries.",
        "The main challenge is intermittency: the sun does not always shine and the wind does not always blow. Grid-scale batteries, pumped hydro storage and better transmission lines are needed to balance supply and demand.",
        "Governments are supporting the transition through tax credits, auctions for new capacity and targets to phase out coal power by 2040."]),
    ("history-of-roman-empire.pdf", "A Short History of the Roman Empire", [
        "Rome began as a small city-state on the Tiber and grew into a republic that conquered the Mediterranean. After Julius Caesar's death, his heir Augustus became the first emperor in 27 BC and began two centuries of relative peace, the Pax Romana.",
        "At its height under Trajan, the empire stretched from Britain to Mesopotamia. Roman roads, aqueducts, law and the Latin language shaped European civilization for a thousand years.",
        "Economic troubles, civil wars and pressure from migrating peoples weakened the western empire, which fell in 476 AD, while the eastern Byzantine empire lasted until 1453."]),
    ("nutrition-and-health-guide.pdf", "A Practical Guide to Nutrition and Health", [
        "A healthy diet is built on vegetables, fruit, whole grains, legumes, nuts and lean protein. Limiting sugary drinks, processed meat and refined carbohydrates lowers the risk of heart disease and type 2 diabetes.",
        "Adults need about 25 to 30 grams of fibre each day, and most people eat far less. Fibre feeds gut bacteria, improves digestion and helps control blood sugar and cholesterol.",
        "Regular exercise, seven to nine hours of sleep and managing stress matter as much as food. Small, sustainable changes work better than strict short-term diets."]),
    ("machine-learning-in-healthcare.pdf", "Machine Learning in Healthcare", [
        "Machine learning models can detect diabetic retinopathy, skin cancer and lung nodules from medical images with accuracy comparable to specialists. They are used to prioritize urgent scans and to give doctors a second opinion.",
        "Hospitals also use predictive models to estimate which patients are at risk of sepsis or readmission. These systems learn patterns from electronic health records.",
        "Challenges include biased training data, patient privacy, explaining model decisions to clinicians and getting regulatory approval before deployment."]),
    ("cybersecurity-best-practices.pdf", "Cybersecurity Best Practices for Small Businesses", [
        "Most breaches begin with phishing emails or stolen passwords. Staff should use a password manager, unique passwords for every service and multi-factor authentication on all important accounts.",
        "Keep operating systems and software updated, because attackers exploit known vulnerabilities within days of a patch being released. Back up important data offline and test that the backups can be restored.",
        "Prepare an incident response plan that names who to call, how to isolate infected machines and how to notify customers and regulators."]),
    ("space-exploration-timeline.pdf", "A Timeline of Space Exploration", [
        "The space age began in 1957 when the Soviet Union launched Sputnik, the first artificial satellite. Yuri Gagarin became the first human in orbit in 1961, and Apollo 11 landed Neil Armstrong and Buzz Aldrin on the Moon in 1969.",
        "Later decades brought space stations, the Space Shuttle, the Hubble telescope and robotic rovers on Mars. The International Space Station has been continuously occupied since 2000.",
        "Today private companies launch reusable rockets, and agencies plan to return astronauts to the Moon and eventually send crews to Mars."]),
    ("blockchain-explained.pdf", "Blockchain Technology Explained", [
        "A blockchain is a shared ledger in which transactions are grouped into blocks, and each block contains the cryptographic hash of the previous one. Changing an old record would break every later hash, so tampering is easy to detect.",
        "Networks such as Bitcoin and Ethereum use consensus mechanisms like proof of work or proof of stake to agree on the next block without a central authority.",
        "Uses beyond cryptocurrency include supply chain tracking, digital identity and smart contracts, although scalability and energy use remain concerns."]),
    ("urban-planning-sustainable-cities.pdf", "Urban Planning for Sustainable Cities", [
        "Sustainable cities reduce car dependence by combining housing, shops and jobs in walkable neighbourhoods served by frequent public transit. Compact development also protects farmland and reduces infrastructure costs.",
        "Green roofs, street trees and permeable pavements cool cities and absorb storm water. Cycling networks and low-traffic streets improve safety and public health.",
        "Affordable housing policy is essential so that sustainability improvements do not push out lower-income residents."]),
    ("intro-to-python-programming.pdf", "Introduction to Python Programming", [
        "Python is a readable, general-purpose programming language used for web development, data analysis, automation and artificial intelligence. Its simple syntax uses indentation to mark blocks of code.",
        "Core concepts include variables, lists, dictionaries, loops, functions and classes. The standard library offers modules for files, dates, networking and testing, and pip installs thousands of third-party packages.",
        "Beginners should practise by writing small programs, reading other people's code and using virtual environments to keep project dependencies separate."]),
    ("deep-learning-image-recognition.pdf", "Deep Learning for Image Recognition", [
        "Convolutional neural networks learn visual features directly from pixels. Early layers detect edges and textures, while deeper layers recognize shapes, objects and faces.",
        "The ImageNet competition in 2012 was a turning point when AlexNet cut the error rate dramatically using GPUs. Later architectures such as ResNet and Vision Transformers pushed accuracy beyond human level on some benchmarks.",
        "Applications include medical imaging, self-driving cars, quality inspection in factories and photo search on phones."]),
    ("ancient-egypt-civilization.pdf", "Ancient Egypt: Life Along the Nile", [
        "Egyptian civilization grew along the Nile, whose annual flood left fertile soil for wheat and barley. Strong central government under the pharaohs organized irrigation, grain storage and monumental building.",
        "The pyramids at Giza were built as royal tombs more than four thousand years ago. Hieroglyphic writing, mummification and a rich religion centred on the afterlife are lasting features of the culture.",
        "Egypt was conquered by Alexander the Great and later became a Roman province after the death of Cleopatra in 30 BC."]),
    ("global-economy-outlook-2026.pdf", "Global Economic Outlook 2026", [
        "Global growth is expected to remain moderate at about three percent as inflation eases and central banks begin to lower interest rates. Consumer spending is resilient in most advanced economies.",
        "Emerging markets benefit from lower energy prices but face high debt costs and a strong dollar. Trade tensions and supply chain disruptions remain the main downside risks.",
        "Investment in artificial intelligence and clean energy is expected to be a major driver of productivity and employment over the coming decade."]),
    ("ethics-of-artificial-intelligence.pdf", "The Ethics of Artificial Intelligence", [
        "As AI systems make decisions about loans, hiring and policing, fairness becomes a central concern. Models trained on historical data can reproduce discrimination unless they are audited and corrected.",
        "Transparency and accountability are also important: people affected by an automated decision should be able to understand it and to appeal. Privacy and consent matter when training data comes from personal information.",
        "Researchers and regulators are developing standards for safety testing, human oversight and responsible deployment of powerful AI systems."]),
]

DOCXS = [
    ("meeting-minutes-q3-planning.docx", "Meeting Minutes: Q3 Planning", [
        "Attendees: Maria, Jonas, Priya and Sam. The team reviewed progress on the mobile app and agreed to move the beta release to the end of September.",
        "Action items: Priya will finish the payment integration by Friday. Jonas will fix the login bugs reported by testers. Sam will prepare the marketing launch checklist.",
        "Next meeting is scheduled for the first Monday of October to review beta feedback."]),
    ("employee-handbook-leave-policy.docx", "Employee Handbook: Leave Policy", [
        "Full-time employees receive twenty days of paid vacation each year, accrued monthly. Unused days up to five may be carried over into the next calendar year.",
        "Sick leave is separate from vacation. Employees may take up to ten paid sick days per year, and a doctor's note is required for absences longer than three consecutive days.",
        "Parental leave is sixteen weeks at full pay for either parent. Requests should be submitted to human resources at least thirty days in advance where possible."]),
    ("resume-software-engineer.docx", "Resume: Alex Morgan, Software Engineer", [
        "Software engineer with six years of experience building web services in Python and Go. Led a team of four to migrate a monolith to microservices on AWS, reducing deployment time by seventy percent.",
        "Skills: Python, Go, SQL, PostgreSQL, Docker, Kubernetes, REST APIs, continuous integration and test-driven development.",
        "Education: Bachelor of Science in Computer Science, University of British Columbia."]),
    ("project-status-report-website.docx", "Project Status Report: Website Redesign", [
        "The website redesign is on schedule and within budget. The new design system and homepage are complete, and the product pages are in development.",
        "Risks: content migration is taking longer than planned because many old pages need rewriting. We recommend adding one writer for two weeks.",
        "Next milestones: usability testing in week six and public launch in week ten."]),
    ("rental-agreement-template.docx", "Residential Rental Agreement", [
        "This agreement is made between the landlord and the tenant for the rental of the property for a term of twelve months. Monthly rent is due on the first day of each month.",
        "The tenant shall pay a security deposit equal to one month's rent, refundable at the end of the tenancy less any deductions for damage beyond normal wear and tear.",
        "Either party may end the tenancy by giving sixty days written notice after the first term. Pets are not permitted without written consent of the landlord."]),
    ("marketing-plan-product-launch.docx", "Marketing Plan: Product Launch", [
        "Our target audience is small business owners aged 25 to 45 who need simple accounting tools. The launch message focuses on saving time and avoiding tax-season stress.",
        "Channels include email newsletters, search advertising, partnerships with business podcasts and a free trial offer. The launch budget is forty thousand dollars over three months.",
        "Success metrics are ten thousand trial sign-ups, a twenty percent trial-to-paid conversion rate and a customer acquisition cost under one hundred dollars."]),
    ("customer-feedback-summary.docx", "Customer Feedback Summary", [
        "Customers praise the product's ease of use and fast support responses. The most requested feature is integration with popular calendar applications.",
        "The main complaints concern slow loading on older phones and confusing pricing tiers. Several users asked for a clearer comparison of the plans.",
        "Overall satisfaction score is 4.4 out of 5, up from 4.1 last quarter."]),
    ("onboarding-checklist.docx", "New Employee Onboarding Checklist", [
        "Before the first day: send the welcome email, order the laptop, create accounts for email, chat and the code repository, and assign a buddy.",
        "First week: office tour, security training, meet the team, review the product roadmap and complete the first small task together with the buddy.",
        "First month: set goals with the manager, finish compliance courses and give feedback on the onboarding process."]),
    ("travel-itinerary-japan.docx", "Travel Itinerary: Ten Days in Japan", [
        "Days one to four in Tokyo: visit Senso-ji temple, the Shibuya crossing, the Tsukiji outer market and a day trip to Nikko. Buy a Suica card for trains and subways.",
        "Days five to seven in Kyoto: Fushimi Inari shrine, the bamboo grove in Arashiyama and a traditional tea ceremony. Travel by bullet train from Tokyo in about two hours.",
        "Days eight to ten: Osaka for street food in Dotonbori, then Hiroshima and the island of Miyajima before flying home."]),
    ("research-proposal-ai-education.docx", "Research Proposal: AI Tutors in Education", [
        "This study will investigate whether AI tutoring systems improve learning outcomes in high school mathematics. Students will be randomly assigned to an AI tutor group or a control group.",
        "We will measure test scores, engagement and student confidence over one semester, and interview teachers about how the tool fits into their classes.",
        "The expected contribution is evidence on when AI tutors help, which students benefit most and what safeguards schools need."]),
]

TXTS = [
    ("sourdough-bread-recipe.txt", "Sourdough Bread Recipe", [
        "Ingredients: 500 g bread flour, 350 g water, 100 g active sourdough starter and 10 g salt.",
        "Mix everything until no dry flour remains and rest for thirty minutes. Fold the dough four times over two hours, then shape it into a round loaf and refrigerate overnight.",
        "Bake in a preheated Dutch oven at 230 degrees Celsius for twenty minutes covered and twenty-five minutes uncovered until the crust is deep golden brown."]),
    ("chocolate-chip-cookies-recipe.txt", "Chocolate Chip Cookies", [
        "Ingredients: 225 g butter, 200 g brown sugar, 100 g white sugar, 2 eggs, 300 g flour, 1 teaspoon baking soda and 300 g chocolate chips.",
        "Cream the butter and sugars, beat in the eggs, then fold in the flour, baking soda and chocolate chips. Chill the dough for one hour.",
        "Bake spoonfuls of dough at 180 degrees Celsius for twelve minutes until the edges are golden and the centres are still soft."]),
    ("marathon-training-plan.txt", "Sixteen-Week Marathon Training Plan", [
        "Run four days a week: one easy run, one tempo run, one interval session and one long run that grows from 10 to 32 kilometres.",
        "Increase weekly mileage by no more than ten percent. Every fourth week is a recovery week with reduced distance.",
        "In the last three weeks taper the mileage, sleep well, eat plenty of carbohydrates and avoid trying new shoes or food on race day."]),
    ("reading-list-ai.txt", "Reading List: Artificial Intelligence", [
        "Start with a general introduction to machine learning, then read about neural networks, optimization and evaluation of models.",
        "Recommended topics: natural language processing, computer vision, reinforcement learning and the ethics of artificial intelligence.",
        "For depth, read the original papers on attention, word embeddings and convolutional networks, and implement a small model yourself."]),
    ("shopping-list-weekly.txt", "Weekly Shopping List", [
        "Produce: spinach, tomatoes, bananas, apples, carrots, onions and garlic.",
        "Dairy and protein: milk, eggs, Greek yoghurt, chicken breast, lentils and tofu.",
        "Pantry: rice, pasta, olive oil, coffee, oats and whole wheat bread."]),
    ("python-tips.txt", "Python Tips", [
        "Use list comprehensions for simple transformations, but switch to a normal loop when the logic gets complicated.",
        "Prefer f-strings for formatting, use pathlib for file paths and use context managers so files are always closed.",
        "Write small functions, add type hints and run tests with pytest before every commit."]),
    ("interview-questions-data-science.txt", "Data Science Interview Questions", [
        "Explain the difference between supervised and unsupervised learning, and give an example of each.",
        "What is overfitting and how can regularization, cross-validation and more data reduce it? How do precision and recall differ?",
        "Describe how you would design an experiment to test whether a new recommendation algorithm increases sales."]),
    ("book-review-sapiens.txt", "Book Review: Sapiens", [
        "Yuval Noah Harari's Sapiens tells the history of humankind from the cognitive revolution to the present day. It argues that shared myths such as money, nations and religion let large groups cooperate.",
        "The writing is lively and thought-provoking, although some historians question the book's sweeping generalizations.",
        "Recommended for readers who want a broad view of how biology, agriculture and technology shaped human societies."]),
    ("poem-autumn.txt", "Autumn", [
        "The maple lets its crimson letters fall, and the evening wind reads each one to the stream.",
        "Geese write their quiet arrows on the sky, pointing south toward warmer, softer light.",
        "I walk the gold-lined path and learn again that every ending is a kind of colour."]),
    ("lecture-notes-linear-algebra.txt", "Lecture Notes: Linear Algebra", [
        "A vector space is a set closed under addition and scalar multiplication. A basis is a linearly independent set that spans the space, and its size is the dimension.",
        "A matrix represents a linear transformation. Eigenvectors are directions that the transformation only stretches, and the stretch factor is the eigenvalue.",
        "Singular value decomposition factors any matrix and underlies principal component analysis and many recommender systems."]),
    ("workout-routine.txt", "Weekly Workout Routine", [
        "Monday and Thursday are strength days: squats, bench press, rows and overhead press for three sets of eight repetitions.",
        "Tuesday and Saturday are cardio: thirty minutes of running or cycling at a steady pace. Wednesday is mobility and stretching.",
        "Sunday is rest. Eat enough protein, drink water and sleep at least seven hours to recover."]),
    ("gardening-tips-tomatoes.txt", "Gardening Tips: Growing Tomatoes", [
        "Plant tomato seedlings after the last frost in a sunny spot with at least six hours of direct light. Bury the stem deeply so that extra roots form.",
        "Water deeply and regularly at the base of the plant, add mulch to keep moisture in and stake the plants to support heavy fruit.",
        "Pinch off suckers, feed with a balanced fertilizer and watch for blight and hornworms."]),
    ("movie-watchlist.txt", "Movie Watchlist", [
        "Science fiction: Arrival, Blade Runner 2049, Ex Machina and Interstellar.",
        "Drama: Parasite, The Social Network, Whiplash and Moonlight.",
        "Documentaries: Free Solo, The Social Dilemma and Won't You Be My Neighbor."]),
    ("git-cheatsheet.txt", "Git Cheat Sheet", [
        "Basics: git status shows changes, git add stages them, git commit saves a snapshot and git push uploads commits to the remote repository.",
        "Branching: git switch -c feature creates a branch, git merge combines branches and git rebase replays commits on top of another branch.",
        "Undo: git restore discards changes in a file, git revert undoes a commit safely and git stash saves unfinished work."]),
]

# --------------------------------------------------------------------------- tables
CSVS = {
    "sales-2025-by-region.csv": (["region", "quarter", "units_sold", "revenue_usd"], [
        ["North", "Q1", 1200, 96000], ["North", "Q2", 1350, 108000], ["South", "Q1", 900, 72000],
        ["South", "Q2", 980, 78400], ["East", "Q1", 1500, 120000], ["West", "Q1", 700, 56000]]),
    "student-grades-fall.csv": (["student", "course", "midterm", "final"], [
        ["Ava", "Math", 88, 92], ["Ben", "Math", 75, 80], ["Chloe", "Physics", 91, 95],
        ["Dev", "Physics", 68, 74], ["Ella", "Chemistry", 82, 85]]),
    "inventory-warehouse.csv": (["sku", "item", "quantity", "location"], [
        ["A100", "Laptop stand", 140, "Aisle 1"], ["B220", "USB-C cable", 900, "Aisle 4"],
        ["C310", "Desk lamp", 75, "Aisle 2"], ["D415", "Monitor", 60, "Aisle 3"]]),
    "website-traffic-monthly.csv": (["month", "visitors", "page_views", "bounce_rate"], [
        ["January", 12000, 30500, "46%"], ["February", 13400, 33200, "44%"], ["March", 15100, 39800, "41%"],
        ["April", 16800, 42500, "40%"]]),
    "stock-prices-sample.csv": (["date", "ticker", "open", "close"], [
        ["2026-03-02", "ACME", 101.2, 103.5], ["2026-03-03", "ACME", 103.6, 102.1],
        ["2026-03-04", "ACME", 102.0, 105.4], ["2026-03-05", "ACME", 105.5, 107.0]]),
}

XLSXS = {
    "household-budget-2026.xlsx": ("Budget", ["Category", "Monthly (CAD)"], [
        ["Rent", 1800], ["Groceries", 650], ["Transport", 180], ["Utilities", 220], ["Savings", 500]]),
    "project-timesheet.xlsx": ("Hours", ["Employee", "Project", "Hours"], [
        ["Maria", "Website", 32], ["Jonas", "Mobile app", 40], ["Priya", "Payments", 36], ["Sam", "Marketing", 28]]),
    "class-schedule.xlsx": ("Schedule", ["Day", "Course", "Room"], [
        ["Monday", "Applied AI", "SCI 201"], ["Tuesday", "Databases", "SCI 105"],
        ["Wednesday", "Applied AI lab", "SCI 310"], ["Thursday", "Statistics", "ARTS 12"]]),
    "expense-report-q3.xlsx": ("Expenses", ["Item", "Department", "Amount (USD)"], [
        ["Conference travel", "Engineering", 2400], ["Software licences", "Engineering", 1800],
        ["Ad campaign", "Marketing", 5200], ["Office supplies", "Operations", 310]]),
}


# --------------------------------------------------------------------------- writers
def write_pdf(path: Path, title: str, paragraphs: list[str]) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(60, 60, 535, 100), title, fontsize=18, fontname="helv")
    page.insert_textbox(pymupdf.Rect(60, 110, 535, 780), "\n\n".join(paragraphs), fontsize=11, fontname="helv")
    doc.save(path)
    doc.close()


def write_docx(path: Path, title: str, paragraphs: list[str]) -> None:
    doc = Document()
    doc.add_heading(title, level=1)
    for paragraph in paragraphs:
        doc.add_paragraph(paragraph)
    doc.save(path)


def write_txt(path: Path, title: str, paragraphs: list[str]) -> None:
    path.write_text(title + "\n\n" + "\n\n".join(paragraphs) + "\n", encoding="utf-8")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    for name, title, paragraphs in PDFS:
        write_pdf(OUT / name, title, paragraphs)
    for name, title, paragraphs in DOCXS:
        write_docx(OUT / name, title, paragraphs)
    for name, title, paragraphs in TXTS:
        write_txt(OUT / name, title, paragraphs)
    for name, (header, rows) in CSVS.items():
        with open(OUT / name, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
    for name, (sheet, header, rows) in XLSXS.items():
        workbook = Workbook()
        workbook.active.title = sheet
        workbook.active.append(header)
        for row in rows:
            workbook.active.append(row)
        workbook.save(OUT / name)

    # Images that contain writing, to try OCR (photos without text are described by the captioning model).
    for name, lines in {
        "meeting-agenda-slide.png": ["Project Kickoff Meeting", "Agenda", "1. Budget review for Q4", "2. Hiring plan and deadlines", "3. Website launch schedule"],
        "whiteboard-todo.png": ["TODO this week", "- finish the literature review", "- email the supervisor", "- book the demo room"],
    }.items():
        image = Image.new("RGB", (1200, 700), "white")
        draw = ImageDraw.Draw(image)
        for i, line in enumerate(lines):
            draw.text((60, 60 + i * 110), line, fill="black", font_size=60 if i == 0 else 48)
        image.save(OUT / name)

    # An exact duplicate and a near duplicate, for the similarity labels.
    shutil.copy(OUT / "sourdough-bread-recipe.txt", OUT / "sourdough-bread-recipe-copy.txt")
    cookies = (OUT / "chocolate-chip-cookies-recipe.txt").read_text(encoding="utf-8")
    (OUT / "chocolate-chip-cookies-recipe-v2.txt").write_text(
        cookies.replace("twelve minutes", "ten minutes").replace("golden", "light golden"), encoding="utf-8")

    print(f"Wrote {len(list(OUT.iterdir()))} files to {OUT}")


if __name__ == "__main__":
    main()
