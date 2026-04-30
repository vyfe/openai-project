from model.repositories.model_meta_repository import get_system_prompt_by_id, get_system_prompts_by_group


def fetch_system_prompt(prompt_id: int):
    return get_system_prompt_by_id(prompt_id)


def fetch_system_prompts_grouped():
    return get_system_prompts_by_group()
