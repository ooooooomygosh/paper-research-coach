import type { LibraryTopics } from "./library-search";

export type TopicFilter = {
  topics: LibraryTopics;
  value: string;
  onChange: (value: string) => void;
};

export default function TopicPicker({
  filter,
  label = "论文主题",
}: {
  filter: TopicFilter;
  label?: string;
}) {
  return (
    <label className="library-topic-picker">
      <span>主题</span>
      <select
        aria-label={label}
        value={filter.value}
        onChange={(event) => filter.onChange(event.target.value)}
      >
        {filter.topics.options.map((topic) => (
          <option key={topic.key} value={topic.key}>
            {topic.label}（{topic.count}）
          </option>
        ))}
      </select>
    </label>
  );
}
