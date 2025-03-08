function togglePostContent(postId) {
    var content = document.getElementById('content-' + postId);
    if (content.style.display === 'none') {
        content.style.display = 'block';
    } else {
        content.style.display = 'none';
    }
}