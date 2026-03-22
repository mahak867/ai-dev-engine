from core.orchestrator import Orchestrator
from core.llm import LLM  # your LLM wrapper that knows the 3 models

def main():
    llm = LLM()  # make sure this routes to llama3, deepcoder, gpt-oss
    orchestrator = Orchestrator(llm)

    project_name = "test_project"
    project_request = "CLI calculator with add and subtract"

    orchestrator.generate_project_files(project_name, project_request)

if __name__ == "__main__":
    main()