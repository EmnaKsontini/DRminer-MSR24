// Other important pens.
// Map: https://codepen.io/themustafaomar/pen/ZEGJeZq
// Navbar: https://codepen.io/themustafaomar/pen/VKbQyZ

'use strict'



function $(selector) {
  return document.querySelector(selector)
}

function find(el, selector) {
  let finded
  return (finded = el.querySelector(selector)) ? finded : null
}

function siblings(el) {
  const siblings = []
  for (let sibling of el.parentNode.children) {
    if (sibling !== el) {
      siblings.push(sibling)
    }
  }
  return siblings
}

const showAsideBtn = $('.show-side-btn')
const sidebar = $('.sidebar')
const wrapper = $('#wrapper')

showAsideBtn.addEventListener('click', function () {
  $(`#${this.dataset.show}`).classList.toggle('show-sidebar')
  wrapper.classList.toggle('fullwidth')
})

if (window.innerWidth < 767) {
  sidebar.classList.add('show-sidebar');
}

window.addEventListener('resize', function () {
  if (window.innerWidth > 767) {
    sidebar.classList.remove('show-sidebar')
  }
})

// dropdown menu in the side nav
var slideNavDropdown = $('.sidebar-dropdown');

$('.sidebar .categories').addEventListener('click', function (event) {
  event.preventDefault()

  const item = event.target.closest('.has-dropdown')

  if (! item) {
    return
  }

  item.classList.toggle('opened')

  siblings(item).forEach(sibling => {
    sibling.classList.remove('opened')
  })

  if (item.classList.contains('opened')) {
    const toOpen = find(item, '.sidebar-dropdown')

    if (toOpen) {
      toOpen.classList.add('active')
    }

    siblings(item).forEach(sibling => {
      const toClose = find(sibling, '.sidebar-dropdown')

      if (toClose) {
        toClose.classList.remove('active')
      }
    })
  } else {
    find(item, '.sidebar-dropdown').classList.toggle('active')
  }
})

$('.sidebar .close-aside').addEventListener('click', function () {
  $(`#${this.dataset.close}`).classList.add('show-sidebar')
  wrapper.classList.remove('margin')
})


// Global defaults
Chart.defaults.global.animation.duration = 2000; // Animation duration
Chart.defaults.global.title.display = false; // Remove title
Chart.defaults.global.defaultFontColor = '#71748c'; // Font color
Chart.defaults.global.defaultFontSize = 13; // Font size for every label

// Tooltip global resets
Chart.defaults.global.tooltips.backgroundColor = '#111827'
Chart.defaults.global.tooltips.borderColor = 'blue'

// Gridlines global resets
Chart.defaults.scale.gridLines.zeroLineColor = '#3b3d56'
Chart.defaults.scale.gridLines.color = '#3b3d56'
Chart.defaults.scale.gridLines.drawBorder = false

// Legend global resets
Chart.defaults.global.legend.labels.padding = 0;
Chart.defaults.global.legend.display = false;

// Ticks global resets
Chart.defaults.scale.ticks.fontSize = 12
Chart.defaults.scale.ticks.fontColor = '#71748c'
Chart.defaults.scale.ticks.beginAtZero = false
Chart.defaults.scale.ticks.padding = 10

// Elements globals
Chart.defaults.global.elements.point.radius = 0

// Responsivess
Chart.defaults.global.responsive = true
Chart.defaults.global.maintainAspectRatio = true


// Get the modal
var modal = document.getElementById("myModal");

// Get the button that opens the modal
var btn = document.getElementById("add-project-button");

// Get the <span> element that closes the modal
var span = document.getElementsByClassName("close")[0];

// When the user clicks the button, open the modal 
btn.onclick = function() {
  modal.style.display = "block";
}

// When the user clicks on <span> (x), close the modal
span.onclick = function() {
  modal.style.display = "none";
}

// When the user clicks anywhere outside of the modal, close it
window.onclick = function(event) {
  if (event.target == modal) {
    modal.style.display = "none";
  }
}
// When the user submits the form

let myChart;

// Function to create a chart
function createChart(canvasId,totalCounts) {
  const ctx = document.getElementById(canvasId).getContext('2d');
  if (myChart) {
    myChart.destroy();
  }

  myChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: Object.keys(totalCounts),
      datasets: [{
        label: '# of refactorings',
        data: Object.values(totalCounts),
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
        borderColor: 'rgba(75, 192, 192, 1)',
        borderWidth: 1
      }]
    },
    options: {
      scales: {
        y: {
          beginAtZero: true
        }
      }
    }
  });
}

document.addEventListener('DOMContentLoaded', (event) => {
  // Function to add projects to the dropdown
  function addProjectsToDropdown(projects) {
    var projectDropdown = document.getElementById('project-dropdown');
    projectDropdown.innerHTML = ''; // Clear the dropdown

    projects.forEach((project) => {
      var option = document.createElement('option');
      option.value = project.id;
      projects.forEach((project) => {
        var option = document.createElement('option');
        option.value = project.id;
        option.text = project.repo_path.split("https://github.com/")[1] + " - " + project.commit_hash;
        projectDropdown.appendChild(option);
      });
      projectDropdown.appendChild(option);
    });
  } 
  /*
  // Function to add projects to the dropdown
  function addProjectsToDropdown(projects) {
    var projectDropdown = document.getElementById('project-dropdown');
    projectDropdown.innerHTML = ''; // Clear the dropdown

    projects.forEach((project) => {
      var projectElement = document.createElement('a');
      projectElement.classList.add('dropdown-item', 'custom-control', 'custom-checkbox');
      projectElement.innerHTML = `
        <input type="checkbox" class="custom-control-input" id="${project.id}">
        <label class="custom-control-label" for="${project.id}">${project.repo_path}</label>
      `;
      projectDropdown.appendChild(projectElement);
    });
}*/

  // Fetch projects on page load
  fetch('/get_projects')
    .then(response => response.json())
    .then(data => {
      addProjectsToDropdown(data);
    })
    .catch((error) => {
      console.error('Error:', error);
    });

  // Event listener for the form submission
  document.getElementById('detect-refactorings-form').addEventListener('submit', function(event) {
    event.preventDefault();
    
    event.preventDefault();
    
    fetch('/create_project', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        repo_path: document.getElementById('repo-path').value,
        commit_hash: document.getElementById('commit-hash').value,
      }),
    })
    .then(response => response.json())
    .then(data => {
      console.log('Success:', data);

      // Call the /detect_refactorings endpoint
      fetch('/detect_refactorings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          repo_path: document.getElementById('repo-path').value,
          commit_hash: document.getElementById('commit-hash').value,
          //dockerfile_path: document.getElementById('dockerfile-path').value,
        }),
      })
      .then(response => response.json())
      .then(data => {
        console.log('Success:', data);
        if (data.hasOwnProperty('refactoring_counts')) {
          createChart('myChartModal', data.refactoring_counts);
        }
      })
      .catch((error) => {
        console.error('Error:', error);
      });
    })
    .catch((error) => {
      console.error('Error:', error);
    });
  });

  

  // Event listener for project dropdown change

document.getElementById('project-dropdown').addEventListener('change', function() {
  const selectedOptions = Array.from(this.selectedOptions).map(option => option.value);

  fetch('/get_projects_data', {
      method: 'POST',
      body: JSON.stringify({ projectIds: selectedOptions }),
      headers: {
          'Content-Type': 'application/json'
      },
  })
  .then(response => response.json())
  .then(data => {
      console.log('Success:', data);

      const refactoringCounts = data.refactoring_counts;

      if (myChart) {
          myChart.destroy();
      }
      createChart('myChartProject', refactoringCounts);
  })
  .catch((error) => {
      console.error('Error:', error);
  });
});


});

