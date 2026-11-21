
from src.support_gpt.inference.model import SupportGPT

def main():
    assistant = SupportGPT()

    questions = [
        "How can I track my order?",
        "I cannot log into my account. Can you help?",
    ]

    for question in questions:
        print("\n" + "=" * 60)
        print("CUSTOMER:", question)
        print("=" * 60)

        response = assistant.generate_response(question)

        print("\nSUPPORTGPT:", response)


if __name__ == "__main__":
    main()
