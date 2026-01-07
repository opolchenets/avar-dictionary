from import_export import resources
from import_export.widgets import ForeignKeyWidget
from .models import PhrasebookSection, PhrasebookPhrase

class PhrasebookSectionResource(resources.ModelResource):
    class Meta:
        model = PhrasebookSection

class PhrasebookPhraseResource(resources.ModelResource):
    section = resources.Field(
        column_name='section',
        attribute='section',
        widget=ForeignKeyWidget(PhrasebookSection, 'name')
    )
    
    class Meta:
        model = PhrasebookPhrase
