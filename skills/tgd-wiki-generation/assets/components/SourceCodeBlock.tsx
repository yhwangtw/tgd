import React from 'react';

interface SourceLine {
  number: number;
  text: string;
}

/**
 * Renders source code with per-line anchors for symbol navigation.
 *
 * The lines array is passed as a JSON prop (not JSX children), so MDX
 * never parses `{`, `}`, `**`, or URLs inside the source text.
 * React renders each line as plain text inside <code>, which is exactly
 * what a source browser needs — no markdown, no linkification, no surprises.
 */
export default function SourceCodeBlock({ lines }: { lines: SourceLine[] }) {
  return (
    <div className="tgd-source-code">
      {lines.map((line) => (
        <div
          key={line.number}
          id={`L${line.number}`}
          className="tgd-source-line"
        >
          <a className="tgd-line-no" href={`#L${line.number}`}>
            {line.number}
          </a>
          <code>{line.text}</code>
        </div>
      ))}
    </div>
  );
}
