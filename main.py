from src.agent.agent import ConversationalAgent


agent = ConversationalAgent()

while True:

    question = input("You: ")

    if question.lower() == "exit":
        break

    answer = agent.ask(question)

    print("\nAssistant:")
    print(answer)
