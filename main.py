from src.agent.agent import ask

while True:

    question = input("You: ")

    if question.lower() == "exit":
        break

    answer = ask(question)

    print("\nAssistant:")
    print(answer)