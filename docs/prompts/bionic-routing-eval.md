You are writing test data for a small assistant called Flux. Work in the folder /Users/antranigbaghdassarian/Desktop/harness-partner-testing-full. Do not run the app, do not use the network, and do not edit anything except the one output file named below.

Flux answers a student's questions about their own mail, calendar and coursework. Each question goes to one "route". The Examples table at the end of each file in playbooks/*.md (not RULES.md) lists real questions with their route (second column).

Task:
1. Read the Examples tables in playbooks/*.md. Skip rows whose question is a follow-up that needs an earlier answer ("and Friday?", "the first one", "who sent that?") and rows that open an app, draft a reply, or sync mail.
2. For each remaining row, write 6 different ways a person might type or say the same request: casual wording, one with a typo, one with no punctuation, one very short, and one that looks like a speech-to-text mistake (a misheard name or word). Keep names and dates from the original. Use only made-up content.
3. Also write 60 extra questions that are about the user, about Flux, about their schedule or about their mail, and must NEVER be sent to the web (for example: "who are you", "what am I", "how's my week looking", "anything I forgot", "what do you remember about me"). Give them route "not_web".
4. Also write 25 clear general-knowledge questions that SHOULD go to the web ("who wrote Frankenstein", "capital of Australia") with route "web".
5. Write everything to reason/tests/routing_eval_extra.jsonl, one JSON object per line, exactly: {"q": "<question>", "route": "<route from the table, or not_web, or web>", "kind": "variant", "book": "<playbook name>"}. No duplicates. No commentary in the file.

When finished, reply with how many lines you wrote per route.
