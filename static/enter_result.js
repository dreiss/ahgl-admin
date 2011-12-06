window.addEventListener("load", function() {
  document.getElementById("smart_form").addEventListener("submit", function(evt) {
    evt.preventDefault();
    var fd = new FormData(this);
    var xhr = new XMLHttpRequest();
    var up = xhr.upload;

    fd.append("is_ajax", "1");
    xhr.addEventListener("error", function() {
      document.getElementById("confirmation_space").innerHTML = "Error!";
    });
    xhr.addEventListener("abort", function() {
      document.getElementById("confirmation_space").innerHTML = "Aborted!";
    });
    xhr.addEventListener("load", function() {
      if (xhr.status != 200) {
        document.getElementById("confirmation_space").innerHTML = "Error!";
        return;
      }
      var response = JSON.parse(xhr.responseText.replace(/^for\(;;\);/, ""));
      console.log(response);
      var cspace = document.getElementById("confirmation_space");
      cspace.innerHTML = response.htmls.join("");
      var boxes = cspace.getElementsByClassName("confirm_box");
      for (var i = 0; i < boxes.length; i++) {
        var forms = boxes[i].getElementsByTagName("form");
        if (forms.length == 0) {
          continue;
        }
        forms[0].addEventListener("submit",
          function (box) {
            return function(evt) {
              evt.preventDefault();
              var fd = new FormData(this);
              var xhr = new XMLHttpRequest();

              xhr.addEventListener("error", function() {
                box.appendChild(document.createTextNode("Error!"));
              });
              xhr.addEventListener("abort", function() {
                box.appendChild(document.createTextNode("Aborted!"));
              });
              xhr.addEventListener("load", function() {
                if (xhr.status != 200) {
                  box.appendChild(document.createTextNode("Error!"));
                  return;
                }
                box.appendChild(document.createTextNode(JSON.parse(xhr.responseText.replace(/^for\(;;\);/, "")).message));
              });

              xhr.open(this.method, this.action);
              xhr.send(fd);
            }
          }(boxes[i])
        );
      }
    });

    xhr.open(this.method, this.action);
    xhr.send(fd);
  });
});
