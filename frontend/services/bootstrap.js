/* Starts everything, once the page is ready.

   Moved verbatim from the end of the original file. */

// Init: set "All Time" as active and trigger report
window.addEventListener('DOMContentLoaded', function(){
  init();
  // Set alltime active after init
  setTimeout(()=>{
    quickSelect('alltime');
  },50);
});
