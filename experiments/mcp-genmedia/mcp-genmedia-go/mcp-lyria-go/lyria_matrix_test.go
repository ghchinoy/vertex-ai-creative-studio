// Copyright 2025 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"testing"

	"github.com/mark3labs/mcp-go/mcp"
)

// TestLyriaResourceLinkMatrix completes the cross-cutting sink matrix for lyria at
// the resource_link seam (design #483 P4 Test Plan). The GCS and inline/no-link
// legs are covered by lyria_resource_link_test.go; this adds the local-only and
// both-local+GCS legs and asserts content[0] is preserved byte-for-byte
// (back-compat). Lyria supports a local sink (local_path), a GCS sink, and inline
// audio; a resource_link is emitted only when a GCS object exists.
func TestLyriaResourceLinkMatrix(t *testing.T) {
	// Local-only sink (local_path set, no GCS): text carries the local saved line;
	// no GCS object -> no resource_link; text byte-identical.
	t.Run("local-only sink -> no resource_link, text byte-identical", func(t *testing.T) {
		localText := "Successfully saved audio locally to /tmp/out/track.wav."
		text := mcp.TextContent{Type: "text", Text: localText}
		content := appendLyriaResourceLink([]mcp.Content{text}, "", "", "audio/wav")
		if len(content) != 1 {
			t.Fatalf("local-only produced %d content items, want 1 (no link)", len(content))
		}
		if got := content[0].(mcp.TextContent).Text; got != localText {
			t.Errorf("text drift on local-only path:\n got=%q\nwant=%q", got, localText)
		}
	})

	// Both local+GCS: text carries BOTH the local saved line and the GCS line; one
	// resource_link is appended for the gs:// URI and content[0] is preserved.
	t.Run("both local+GCS -> resource_link present, text byte-identical", func(t *testing.T) {
		bothText := "Successfully saved audio locally to /tmp/out/track.wav. " +
			"Successfully uploaded to gs://my-bucket/lyria_outputs/track.wav."
		text := mcp.TextContent{Type: "text", Text: bothText}
		content := appendLyriaResourceLink([]mcp.Content{text}, "my-bucket", "lyria_outputs/track.wav", "audio/wav")
		if len(content) != 2 {
			t.Fatalf("both sink produced %d content items, want 2 (text + link)", len(content))
		}
		if got := content[0].(mcp.TextContent).Text; got != bothText {
			t.Errorf("text drift on both path (back-compat):\n got=%q\nwant=%q", got, bothText)
		}
		link, ok := content[1].(mcp.ResourceLink)
		if !ok {
			t.Fatalf("content[1] = %T, want mcp.ResourceLink", content[1])
		}
		if link.URI != "gs://my-bucket/lyria_outputs/track.wav" {
			t.Errorf("resource_link URI = %q, want gs://my-bucket/lyria_outputs/track.wav", link.URI)
		}
		if link.MIMEType != "audio/wav" {
			t.Errorf("resource_link MIMEType = %q, want audio/wav", link.MIMEType)
		}
	})
}
