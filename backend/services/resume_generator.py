import json
import time
from typing import Optional, Union

from litellm import completion
from pydantic import BaseModel, ValidationError

from core.config import Settings
from models.Github import GithubProfile, Repository
from models.bootdev import BootDevProfile
from models.leetcode import LeetCodeProfile
from models.resume import Form


class PersonalInfo(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    twitter: str = ""
    website: str = ""


class Experience(BaseModel):
    title: str = ""
    company: str = ""
    duration: str = ""
    description: str = ""


class Project(BaseModel):
    name: str = ""
    description: str = ""
    technologies_used: list[str] = []


class Education(BaseModel):
    degree: str = ""
    institution: str = ""
    year: str = ""


class Resume(BaseModel):
    personal_info: PersonalInfo
    summary: str = ""
    skills: list[str] = []
    experience: list[Experience] = []
    projects: list[Project] = []
    education: list[Education] = []
    achievements: list[str] = []


class ScrapedData(BaseModel):
    github_profile: Optional[GithubProfile] = None
    github_repositories: Optional[list[Repository]] = None
    leetcode_profile: Optional[LeetCodeProfile] = None
    bootdev_profile: Optional[BootDevProfile] = None
    personal_info: Optional[Form] = None


class SummarizedData(BaseModel):
    personal_info: dict = {}
    technical_skills: list[str] = []
    key_projects: list[dict] = []
    learning_achievements: list[str] = []
    problem_solving_stats: dict = {}
    professional_experience_indicators: list[str] = []
    education_background: list[str] = []


def data_summarizer(scraped_data: ScrapedData):
    system_instruction = data_summarizer_sys_prompt()
    scraped_data_dict = scraped_data.model_dump(exclude_none=True)

    user_content = f"""
    summarize the following scraped data for resume creation:
    {json.dumps(scraped_data_dict, indent=2)}
    """

    try:
        print("Summarizing data for resume generation...")
        print("config ", Settings().OPENROUTER_MODEL)
        response = completion(
            model=f"openrouter/{Settings().OPENROUTER_MODEL}",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"}
        )

        # parse json
        summary_json = json.loads(response.choices[0].message.content)
        # validate
        summarized_data = SummarizedData(**summary_json)
        return summarized_data

    except Exception as e:
        print(f"Error summarizing data: {e}")
        return None


def resume_generator(data: Union[ScrapedData, SummarizedData], use_summarizer: Optional[bool] = False):
    if isinstance(data, ScrapedData):
        if use_summarizer:
            summarized_data = data_summarizer(data)
            input_data = summarized_data.model_dump()
            system_instruction = with_data_summarizer()
        else:
            input_data = data.model_dump(exclude_none=True)
            system_instruction = without_data_summarizer()
    else:
        input_data = data.model_dump()
        system_instruction = with_data_summarizer()

    user_content = f"""
    Create a professional resume using this data:
    {json.dumps(input_data, indent=2)}
    """
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds
    try:
        print("Generating resume...")
        print("config ", Settings().OPENROUTER_MODEL)
        response = completion(
            model=f"openrouter/{Settings().OPENROUTER_MODEL}",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"}
        )

        resume_json = json.loads(response.choices[0].message.content)
        for attempt in range(MAX_RETRIES):
            try:
                resume_model = Resume(**resume_json)
                return resume_model.model_dump()
            except ValidationError as ve:
                print(f"Validation error on attempt {attempt + 1}: {ve}")
                if attempt < MAX_RETRIES - 1:
                    print("Retrying resume generation...")
                    error_message = f"ValidationError: {ve.errors()}"
                    retry_user_content = (
                            user_content +
                            f"\n\nThe previous response could not be parsed due to the following validation errors:\n{error_message}\n"
                            "Please fix these issues and return valid JSON matching the required schema."
                    )
                    time.sleep(RETRY_DELAY)
                    response = completion(
                        model=f"openrouter/{Settings().OPENROUTER_MODEL}",
                        messages=[
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": retry_user_content}
                        ],
                        response_format={"type": "json_object"}
                    )
                    resume_json = json.loads(response.choices[0].message.content)
                else:
                    print("Max retries reached. Returning None.")
                    return None
    except Exception as e:
        print(f"Error generating resume: {e}")
        return None


def with_data_summarizer() -> str:
    return """you are an expert resume writer with the experts in creating cool af resumes
    JSON structure: {"personal_info":{"name":"","email":"","phone":"","location":"","linkedin":"","github":"","twitter":"","website":""},"summary":"","skills":[],"experience":[{"title":"","company":"","duration":"","description":""}],"projects":[{"name":"","description":"","technologies_used":["tech1","tech2"]}],"education":[{"degree":"","institution":"","year":""}],"achievements":[""]}
    
    create a professional resume following these guidelines:
    - professional summary highlighting key strengths using STAR (Situation, Task, Action, Result) or CAR (Challenge, Action, Result) methodology
    - transform project data into impressive project descriptions
    - use problem-solving stats to demonstrate analytical capabilities
    - create profesional experience if there's any
    - fill missing information with "[USER INPUT REQUIRED]" placeholders
    - Analyze README files in repositories for additional personal info, education details, work experience, and project descriptions

    return valid JSON only, no markdown."""


def without_data_summarizer() -> str:
    return """You are a professional AI resume writer. Based on the provided scraped user data from GitHub, boot.dev, and leetcode, create a cool af resume.
    Required JSON structure: {"personal_info":{"name":"","email":"","phone":"","location":"","linkedin":"","github":"","twitter":"","website":""},"summary":"","skills":[],"experience":[{"title":"","company":"","duration":"","description":""}],"projects":[{"name":"","description":"","technologies_used":["tech1","tech2"]}],"education":[{"degree":"","institution":"","year":""}],"achievements":[""]}
    
    IMPORTANT INSTRUCTIONS:
    - extract information from the scraped data, including GitHub repository README files for additional context
    - create a professional summary that highlights skills and maybe experience
    - infer projects from github with meaningful descriptions
    - use boot.dev courses to highlight learning journey
    - add leetcode achievements to showcase problem-solving skill
    - generate profesional entries, if the user has any
    - fill missing information with "[USER INPUT REQUIRED]" placeholders
    - make reasonable professional inferences from the available data
    - highlight learning journey
    - focus on impressive and relevant info
    - skip underwhelming stats (e.g. <50 LeetCode problems)
    - Analyze README files in repositories for additional personal info, education details, work experience, and project descriptions

    return valid JSON only, no markdown."""


def data_summarizer_sys_prompt() -> str:
    return """you are an expert data analyst in extracting and summarizing information.

    your task is to analyzed scrapped data from github, leetcode, boot.dev that highlights:
    - Personal info: extract name, location, contact details, and professional links
    - Technical skills: programming languages, frameworks, tools
    - Key projects: impressive GitHub repositories with meaningful descriptions
    - Learning achievements: summarize completed courses, certifications, continuous learning
    - Problem-solving stats: extract leetcode stats
    - Do not include stats or achievements that are underwhelming or unimpressive. For example, 
      do not mention leetcode problem counts below 50, github followers below 200, or any other metric that does not stand out positively to a technical recruiter.
    - Professional indicators: look for patterns suggesting employment, freelance work, or professional experience
    - Education background: infer formal or informal education from courses and project complexity
    - Analyze README files in repositories for additional personal info, education details, work experience, and project descriptions
    
    QUALITY GUIDELINES:
    - prioritize active projects and if applicable recent ones
    - highlight consistent learning patterns
    - extract quantifiable achievements
    - identify professional work patterns
    - focus on career-relevant information

    Return valid JSON only."""
