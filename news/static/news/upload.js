window.eeUploadImage = async function(blobInfo) {
  const data = new FormData();
  data.append('file', blobInfo.blob(), blobInfo.filename());
  const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
  const response = await fetch('/admin/inline-upload/', {method:'POST', credentials:'same-origin', headers:{'X-CSRFToken':csrf}, body:data});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Upload failed');
  return result.location;
};
