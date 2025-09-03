# dashboard_app/forms.py
from django import forms
from .models import Dataset

class UploadDatasetForm(forms.ModelForm):
    class Meta:
        model = Dataset
        fields = ['file']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'accept': '.csv'}),
        }
