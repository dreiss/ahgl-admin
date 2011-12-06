#!/usr/bin/env php
<?php
define('SC2REPLAY_ROOT', getenv('SC2REPLAY_ROOT'));
require_once SC2REPLAY_ROOT.'/mpqfile.php';
require_once SC2REPLAY_ROOT.'/sc2replay.php';
require_once SC2REPLAY_ROOT.'/sc2replayutils.php';
require_once SC2REPLAY_ROOT.'/sc2map.php';

function _main($args) {
  if (count($args) != 2) {
    throw new Exception('usage: replay_info REPLAYFILE.SC2Replay');
  }

  $mpqfile = new MPQFile($args[1]);
  if (!$mpqfile->getState()) {
    throw new Exception('Failed to parse header');
  }

  $replay = $mpqfile->parseReplay();
  if (!$replay) {
    throw new Exception('Failed to parse replay');
  }

  $map_name = $replay->getMapName();
  if (!$map_name) {
    throw new Exception('Failed to get map name');
  }

  $real_players = array();
  $players = $replay->getPlayers();
  if (!$players) {
    throw new Exception('No players listed');
  }
  foreach ($players as $player) {
    if ($player['isObs']) {
      continue;
    }
    $real_players[] = array(
      'name' => $player['name'],
      'race' => $player['race'],
      'lrace' => $player['lrace'],
      'srace' => $player['srace'],
      'color' => $player['color'],
      'scolor' => $player['scolor'],
      'won' => $player['won'],
    );
  }

  $result = array(
    'map_name' => $map_name,
    'players' => $real_players,
  );

  echo json_encode($result), "\n";

  //var_dump($replay);
}

_main($argv);
