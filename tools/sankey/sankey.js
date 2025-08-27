function make_group_default(name) {
  return {
    Name: name,
    Depth: 0,
    Edges: [],
    LeftoverEdge: null,
    Histogram: null,
    Column: null,
    Value: 0,
  };
}


function tableToArray(table) {
  const rows = table.querySelectorAll('tr, thead tr');
  const data = [];
  rows.forEach(row => {
    const cells = row.querySelectorAll('td');
    const rowData = [];
    cells.forEach(cell => {
      if (cell.children.length === 0) {
        rowData.push(cell.textContent.trim());
      } else if (cell.hasAttribute('rowspan')) {
        rowData.push(cell.innerText);
      } else {
        cell.querySelectorAll('paper-tooltip').forEach(ptt => {
          ptt.innerHTML = '';
        });
        rowData.push(cell.children[0].innerText);
      }
    });
    data.push(rowData);
  });
  return data;
}

function GetHistogramNode(histogram) {
  const vardash = document.getElementsByTagName("variations-dash")[0];
  const container = vardash.shadowRoot.querySelector("paper-material");
  const histograms = container.querySelector("histograms-tab");
  const element = histograms.shadowRoot.querySelector(`variations-histogram-entry[id='${histogram}']`);
  // Disgusting.
  const graph_container = element.shadowRoot.children[1].children[6].children[9];

  const numeric_histogram = graph_container.querySelector('variations-numeric-histogram');
  if (numeric_histogram !== null) {
    return numeric_histogram.shadowRoot.querySelector('iron-pages').children[0].shadowRoot.children[1].shadowRoot.children[1].children[3].children[0];
  }

  const table = graph_container.children[0].shadowRoot.children[2].children[0].shadowRoot.children[1].children[3].children[0];
  return table;
}

function GetHistogramData(histogram) {
  return tableToArray(GetHistogramNode(histogram));
}

function get_groups_for_histogram(histogram) {
  const [group, total, ...names] = GetHistogramData(histogram)[0]
  return names;
}

function get_histogram_value(histogram, row, column) {
  const data = GetHistogramData(histogram);
  console.log(histogram, data);
  const [g, r, ...headers] = data[0];

  for (let rn = 1; rn < data.length; rn++) {
    const [group, total, ...values] = data[rn];
    if (group === row) {
      if (column === 'Total') {
        if (r.indexOf('Total') === -1) {
          return parseInt(total.replaceAll(',', ''));
        } else {
          return parseInt(values[0].replaceAll(',', ''));
        }
      }
      return parseInt(values[headers.indexOf(column)].replaceAll(',', ''));
    }
  }
  return -1;
}

function parse_config(config_text) {
  let lines = config_text.trim().split('\n');
  let properties = {};
  let groups = {};

  for (var line of lines) {
    line = line.trim();
    if (line.indexOf(':') !== -1) {
      // This is a property setting line
      let propinfo = line.split(': ', 2);
      properties[propinfo[0]] = propinfo[1];
    } else if (line.indexOf(' => ') !== -1) {
      // This is a group definition
      let groupinfo = line.split(' => ', 2);
      let source = groupinfo[0];
      let destinfo = groupinfo[1].split('/');
      let destination = destinfo[0];
      let histogram = destinfo[1];
      let column = destinfo[2];

      if (!(source in groups)) {
        groups[source] = make_group_default(source);
      }

      if (histogram === '!') {
        histogram = groups[source].Histogram;
      }

      if (destination !== '&') {
        // The group name is well defined, so add it!
        if (!(destination in groups)) {
          groups[destination] = make_group_default(destination);
        }

        groups[destination].Histogram = histogram;

        if (column === '%') {
          groups[source].LeftoverEdge = destination;
        } else {
          groups[destination].Column = column;
        }

        groups[source].Edges.push(destination);
        if (groups[destination].Depth <= groups[source].Depth) {
          groups[destination].Depth = groups[source].Depth+1;
        }

      } else {
        for (var group of get_groups_for_histogram(histogram)) {
          destination = `${histogram}:${group}`;
          column = group;

          if (!(destination in groups)) {
            groups[destination] = make_group_default(destination);
          }
          groups[destination].Histogram = histogram;
          groups[destination].Column = column;
          groups[source].Edges.push(destination);
          if (groups[destination].Depth <= groups[source].Depth) {
            groups[destination].Depth = groups[source].Depth+1;
          }
        }
      }
    }
  }
  return {
    "Groups": groups,
    "Properties": properties,
  };
}


function get_data_for_group(node, groupname, groups) {
  let result = [];
  if (node.Name !== 'Root') {
    if (node.LeftoverEdge !== null && node.Column !== null) {
      node.Value = get_histogram_value(node.Histogram, groupname, node.Column);
      console.log(groupname, node.Column, node.Value);
    }
    for (const target_name of node.Edges) {
      if (target_name === node.LeftoverEdge) { continue; }
      const target = groups[target_name];
      target.Value = get_histogram_value(target.Histogram, groupname, target.Column);
      console.log(groupname, node.Column, node.Value);
      node.Value -= target.Value;
      result.push({
        "From": node.Name,
        "To": target_name,
        "Amount": target.Value + 0
      });
    }
    if (node.LeftoverEdge !== null) {
      groups[node.LeftoverEdge].Value = node.Value;
      result.push({
        "From": node.Name,
        "To": node.LeftoverEdge,
        "Amount": node.Value + 0
      });
    }
  }
  for (const child of node.Edges) {
    result = result.concat(get_data_for_group(groups[child], groupname, groups))
  }
  return result;
}

function export_config_to_fta(config) {
  const groups = config.Groups;
  const groupname = config.Properties.GroupName;
  const map = get_data_for_group(groups.Root, groupname, groups);
  return map.map(e => [e.From, e.To, e.Amount]);
}


function log_data_for_config(config) {
  console.log(JSON.stringify(export_config_to_fta(parse_config(config)), null, 2));
}

function log_in_apc_format(config) {
  const data = export_config_to_fta(parse_config(config));
  const transform = { 'edges': [], 'nodes': [] };
  const nodemap = {};
  for (var ent of data) {
    const [f, t, v] = ent;
    if (!(f in nodemap)) {
      nodemap[f] = {'id': f, 'title': f};
    }
    if (!(t in nodemap)) {
      nodemap[t] = {'id': t, 'title': t};
    }
    transform['edges'].push({
      'source': f,
      'target': t,
      'value': v,
    });
  }
  for (const [k,v] of Object.entries(nodemap)) {
    transform['nodes'].push(v);
  }
  console.log(JSON.stringify(transform, null, 2));
}

const ManifestDemuxerConfig = `
GroupName: Enabled_20250131

Root => Playbacks/Media.HLS.MultivariantPlaylist/Total
Playbacks => InitError/Media.HLS.InitializationError/Total
Playbacks => InitOK/!/%
InitError => &/Media.HLS.InitializationError/*
InitOK => PlaybackError/Media.HLS.PlaybackError/Total
InitOK => PlaybackOK/!/%
PlaybackError => &/!/*`;


const MediaPlayerConfig = `
GroupName: Control_20250131

Root => Playbacks/Media.TimeToMetadata.HLS/Total
Playbacks => InitOK/Media.TimeToFirstFrame.HLS/Total
Playbacks => InitError/!/%
InitOK => WeCantPlay/Media.HLS.UnparsableManifest/Total
InitOK => WeCanPlay/!/%
`;

log_in_apc_format(ManifestDemuxerConfig);
//log_data_for_config(MediaPlayerConfig);
