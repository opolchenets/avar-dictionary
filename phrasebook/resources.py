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
    
    def get_fields(self, **kwargs):
        fields = super().get_fields(**kwargs)
        # Удаляем section_id, если он есть
        return [f for f in fields if f.attribute != 'section_id']
    
    class Meta:
        model = PhrasebookPhrase
        fields = ('id', 'section', 'text', 'translation', 'translit')
        exclude = ('section_id',)
        import_id_fields = []
