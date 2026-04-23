from sources.github_source import GitHubSource
from sources.huggingface_source import HuggingFaceSource
from sources.twitter_source import TwitterSource
from sources.arxiv_source import ArxivSource
from sources.semanticscholar_source import SemanticScholarSource
from sources.pubmed_source import PubMedSource
from sources.journals_source import JournalsSource

SOURCE_REGISTRY = {
    "github": GitHubSource,
    "huggingface": HuggingFaceSource,
    "twitter": TwitterSource,
    "arxiv": ArxivSource,
    "semanticscholar": SemanticScholarSource,
    "pubmed": PubMedSource,
    "journals": Nature, Science, Nature Food, Nature Water, Nature Climate Change, Nature Cities, Science Advances, One Earth, Earth's Future, Cell Reports Sustainability,
}
