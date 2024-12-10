document.addEventListener('DOMContentLoaded', function() {
    const textOnlyDivs = document.querySelectorAll('.text-only-div');

    textOnlyDivs.forEach(div => {
        div.setAttribute('dir', 'ltr');
        div.style.textAlign = 'left';

        div.addEventListener('paste', function(e) {
            e.preventDefault();
            const text = e.clipboardData.getData('text/plain');
            document.execCommand('insertText', false, text);
        });

        div.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();

                // Insert a line break
                const selection = window.getSelection();
                const range = selection.getRangeAt(0);
                const br = document.createElement('br');
                range.deleteContents();
                range.insertNode(br);

                // Move the cursor after the line break
                range.setStartAfter(br);
                range.setEndAfter(br);
                selection.removeAllRanges();
                selection.addRange(range);

                // Ensure the new line is visible
                br.scrollIntoView();
            }
        });

        div.addEventListener('input', function() {
            // Strip HTML tags, but preserve line breaks
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = this.innerHTML.replace(/<br>/gi, '&lt;br&gt;');
            this.textContent = tempDiv.textContent;
            this.innerHTML = this.innerHTML.replace(/&lt;br&gt;/gi, '<br>');

            // Reinforce left-to-right direction after input
            this.setAttribute('dir', 'ltr');
            this.style.textAlign = 'left';
        });
    });
});