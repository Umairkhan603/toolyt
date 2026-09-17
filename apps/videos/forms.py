from django import forms
from .models import VideoSource


class VideoUploadForm(forms.ModelForm):
    rights_confirmed = forms.BooleanField(
        required=True,
        label="Rights & Compliance Confirmation",
        help_text=(
            "I confirm that I own this content or have the necessary permission/license to "
            "download, edit, and publish it. Transformative editing does not automatically "
            "grant permission to use copyrighted material."
        ),
        error_messages={
            'required': 'You must confirm ownership or license rights before uploading.'
        }
    )

    class Meta:
        model = VideoSource
        fields = ('original_file', 'title', 'rights_confirmed')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:ring focus:ring-blue-200',
                'placeholder': 'Optional title for this video'
            }),
            'original_file': forms.FileInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:ring focus:ring-blue-200',
                'accept': 'video/mp4,video/quicktime,video/x-msvideo,video/x-matroska,video/webm'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        rights = cleaned_data.get('rights_confirmed')
        file = cleaned_data.get('original_file')
        if not rights:
            raise forms.ValidationError("Mandatory copyright & rights confirmation is required.")
        if not file:
            raise forms.ValidationError("Please select a valid video file to upload.")
        return cleaned_data


class VideoUrlImportForm(forms.ModelForm):
    rights_confirmed = forms.BooleanField(
        required=True,
        label="Rights & Compliance Confirmation",
        help_text=(
            "I confirm that I own this content or have the necessary permission/license to "
            "import, edit, and publish it. This system does not bypass DRM, access controls, "
            "or copyright detection mechanisms."
        ),
        error_messages={
            'required': 'You must confirm rights before importing a video URL.'
        }
    )

    class Meta:
        model = VideoSource
        fields = ('source_url', 'title', 'rights_confirmed')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:ring focus:ring-blue-200',
                'placeholder': 'Optional title for this video'
            }),
            'source_url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:ring focus:ring-blue-200',
                'placeholder': 'https://example.com/authorized-video.mp4'
            }),
        }

    def clean_source_url(self):
        url = self.cleaned_data.get('source_url')
        if not url:
            raise forms.ValidationError("A valid video URL is required.")
        # Check URL protocol
        if not (url.startswith('http://') or url.startswith('https://')):
            raise forms.ValidationError("URL must use HTTP or HTTPS protocol.")
        return url
