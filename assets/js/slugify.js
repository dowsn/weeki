$(document).ready(function() {

  const slugify = (val) => {
    return val.toString().toLowerCase().trim()
      .replace(/&/g, '-and-') 
      .replace(/[\s\W-]+/g, '-')
  };
  
  const titleInput = $('input[name=name]');
  const slugInput = $('input[name=slug]');

  titleInput.on('keyup', function(e) {
    slugInput.attr('value', slugify(titleInput.val()));
  });
               
});