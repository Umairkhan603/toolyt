from django import forms
from .models import ProcessingJob


class ProcessingJobForm(forms.ModelForm):
    class Meta:
        model = ProcessingJob
        fields = (
            'clip_duration',
            'crop_mode',
            'start_time',
            'end_time',
            'caption_enabled',
            'caption_style',
            'watermark_enabled',
            'watermark_text',
            'audio_volume'
        )
        widgets = {
            'clip_duration': forms.Select(attrs={'class': 'form-select w-full border rounded-lg p-2.5 bg-gray-50 border-gray-300 text-gray-900 focus:ring-blue-500 focus:border-blue-500'}),
            'crop_mode': forms.Select(attrs={'class': 'form-select w-full border rounded-lg p-2.5 bg-gray-50 border-gray-300 text-gray-900 focus:ring-blue-500 focus:border-blue-500'}),
            'caption_style': forms.Select(attrs={'class': 'form-select w-full border rounded-lg p-2.5 bg-gray-50 border-gray-300 text-gray-900 focus:ring-blue-500 focus:border-blue-500'}),
            'start_time': forms.NumberInput(attrs={'class': 'form-input w-full border rounded-lg p-2.5 bg-gray-50 border-gray-300 text-gray-900', 'step': '0.1', 'min': '0'}),
            'end_time': forms.NumberInput(attrs={'class': 'form-input w-full border rounded-lg p-2.5 bg-gray-50 border-gray-300 text-gray-900', 'step': '0.1', 'min': '0'}),
            'watermark_text': forms.TextInput(attrs={'class': 'form-input w-full border rounded-lg p-2.5 bg-gray-50 border-gray-300 text-gray-900', 'placeholder': '@yourhandle or Brand'}),
            'audio_volume': forms.NumberInput(attrs={'class': 'form-input w-full border rounded-lg p-2.5 bg-gray-50 border-gray-300 text-gray-900', 'step': '0.1', 'min': '0.0', 'max': '3.0'}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_time') or 0.0
        end = cleaned.get('end_time')
        if end is not None and end <= start:
            raise forms.ValidationError("End timestamp must be greater than start timestamp.")
        return cleaned
