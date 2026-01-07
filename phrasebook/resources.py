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
    
    def get_or_init_instance(self, instance_loader, row):
        """Используем section и text для поиска существующей записи."""
        try:
            section_name = row.get('section', '')
            text = row.get('text', '')
            
            if section_name and text:
                section = PhrasebookSection.objects.get(name=section_name)
                instance = PhrasebookPhrase.objects.get(section=section, text=text)
                return instance, False
        except (PhrasebookSection.DoesNotExist, PhrasebookPhrase.DoesNotExist):
            pass
        
        return super().get_or_init_instance(instance_loader, row)
    
    class Meta:
        model = PhrasebookPhrase
        fields = ('id', 'section', 'text', 'translation', 'translit')
        exclude = ('section_id',)
        import_id_fields = []
        skip_unchanged = True
