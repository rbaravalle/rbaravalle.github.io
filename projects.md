---
layout: page
title: Projects
permalink: /projects/
---

{% for p in site.data.projects %}
{%- assign img_path = '/assets/projects/' | append: p.image -%}
{%- assign img_file = site.static_files | where: "path", img_path | first -%}
<div class="project">
  {%- if img_file %}
  <img class="project-image" src="{{ img_path | relative_url }}" alt="{{ p.title }}">
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
