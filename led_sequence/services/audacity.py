
def config_to_audacity_labels_episodes(config):

    audacity_formatted_output = ''
    section_start_episode = 0
    for bpmSection in config["bpmSections"]:

        num_episodes = bpmSection["numEpisodes"]
        start_seconds = bpmSection["startSeconds"]
        bpm = bpmSection["bpm"]
        beats_per_episode = bpmSection["beatsPerEpisode"]

        episode_duration = 60 / bpm * beats_per_episode

        section_episodes = [{"index": i + section_start_episode,
                             "start_time": start_seconds + i * episode_duration} for i in range(num_episodes)]
        audacity_labels = [ f'{episode["start_time"]}\t{episode["start_time"]}\te {episode["index"]}\n' for episode in section_episodes]
        
        audacity_formatted_output += ''.join(audacity_labels)
        section_start_episode += num_episodes

    return audacity_formatted_output

def config_to_audacity_labels_beats(config):

    audacity_formatted_output = ''
    section_start_episode = 0
    for bpmSection in config["bpmSections"]:

        num_episodes = bpmSection["numEpisodes"]
        start_seconds = bpmSection["startSeconds"]
        bpm = bpmSection["bpm"]
        beats_per_episode = bpmSection["beatsPerEpisode"]

        num_beats = num_episodes * beats_per_episode
        beat_duration = 60 / bpm

        section_beats = [{"index": i + section_start_episode,
                             "start_time": start_seconds + i * beat_duration} for i in range(num_beats)]
        audacity_labels = [ f'{beat["start_time"]}\t{beat["start_time"]}\tb {beat["index"]}\n' for beat in section_beats]
        
        audacity_formatted_output += ''.join(audacity_labels)
        section_start_episode += num_episodes

    return audacity_formatted_output
