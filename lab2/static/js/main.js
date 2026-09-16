import { $ } from './jquery.js';

const gallery = $('.gallery');
const viewer = $('#viewer');
const viewerImage = $('#viewer-image');
const body = $('body');

function openViewer(image) {
    viewerImage.attr('src', image.currentSrc || image.src);
    viewerImage.attr('alt', image.alt);
    viewer.attr('aria-hidden', 'false');
    viewer.addClass('open');
    body.addClass('viewer-open');
}

function closeViewer() {
    viewer.removeClass('open');
    viewer.attr('aria-hidden', 'true');
    body.removeClass('viewer-open');
}

gallery.on('click', (event) => {
    const image = event.target.closest('img');

    if (image && gallery[0].contains(image)) {
        openViewer(image);
    }
});

viewer.click(closeViewer);

$(document).on('keydown', (event) => {
    if (event.key === 'Escape') {
        closeViewer();
    }
});
