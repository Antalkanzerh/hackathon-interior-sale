document.addEventListener('DOMContentLoaded', function(){
    // simple tab/category filtering (front-end)
    document.querySelectorAll('.tab').forEach(function(btn){
        btn.addEventListener('click', function(){
            var cat = this.dataset.cat
            // naive: append ?category= to the current URL
            var url = new URL(window.location.href)
            url.searchParams.set('category', cat)
            window.location.href = url.toString()
        })
    })

    // search form submit on enter
    var searchForm = document.getElementById('search-form')
    if(searchForm){
        searchForm.addEventListener('submit', function(e){
            // default behavior is fine (GET)
        })
    }

    // site logo is now a normal link to home (no JS required)
})
