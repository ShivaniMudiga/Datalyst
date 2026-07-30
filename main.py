from src.agent.agent import ConversationalAgent
from src.utils.uuid_manager import create_thread_id


print("===================================")
print("        TalkToMyData")
print("===================================")
print("1. New Chat")
print("2. Resume Chat")

choice = input("\nChoose an option (1/2): ")

if choice == "1":
    thread_id = create_thread_id()
    print(f"\n✅ New chat created!")
    print(f"Thread ID: {thread_id}")

elif choice == "2":
    thread_id = input("\nEnter Thread ID: ").strip()

else:
    print("Invalid choice.")
    exit()

agent = ConversationalAgent(thread_id)

print("\nType 'exit' to quit.\n")

while True:

    question = input("You: ")

    if question.lower() == "exit":
        break

    answer = agent.ask(question)

    print("\nAssistant:")
    print(answer)