from django import forms
from django.core import validators
from django.core.files.uploadedfile import InMemoryUploadedFile

from chat.models import Documento


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        if self.required and not result:
            raise forms.ValidationError(
                self.error_messages['required'], code='required'
            )
        return result


class ImportarDocumentosForm(forms.Form):
    documentos = MultipleFileField(
        label='Selecione os PDFs',
        validators=[validators.FileExtensionValidator(['pdf'])],
    )

    def __init__(self, *args, **kwargs):
        kwargs['use_required_attribute'] = False
        super().__init__(*args, **kwargs)
        self.fields['documentos'].widget.attrs['autocomplete'] = 'off'
        self.fields['documentos'].widget.attrs['accept'] = '.pdf'

    def save(self, tipos=None):
        documentos: list[InMemoryUploadedFile] = self.cleaned_data[
            'documentos'
        ]
        tipos = tipos or {}

        for i, documento in enumerate(documentos):
            tipo = tipos.get(str(i), Documento.Tipo.MANUAL)
            Documento(nome=documento.name, arquivo=documento, tipo=tipo).save()


class ImportarSkillForm(forms.Form):
    arquivo = forms.FileField(
        label='PDF do documento',
        validators=[validators.FileExtensionValidator(['pdf'])],
    )
