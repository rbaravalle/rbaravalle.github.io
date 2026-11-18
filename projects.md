---
layout: page
title: Projects
permalink: /projects/
---

{% for p in site.data.projects %}
<div class="project">
  {%- if p.image %}
  <img class="project-image" src="{{ '/assets/projects/' | append: p.image | relative_url }}" alt="{{ p.title }}">
  {%- endif %}
  <div class="project-body">
    <h2 class="project-title">{{ p.title }}</h2>
    <p class="project-meta">{{ p.meta }}</p>
    <p>{{ p.description }}</p>
    {%- if p.links.size > 0 %}
    <ul class="project-links">
      {%- for l in p.links %}
      <li><a href="{{ l.url }}">{{ l.label }}</a></li>
      {%- endfor %}
    </ul>
    {%- endif %}
  </div>
</div>
{% endfor %}
