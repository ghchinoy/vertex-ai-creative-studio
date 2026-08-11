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

// TestAppendLyriaResourceLinkGCS asserts the GCS-sink result shape for lyria (a
// single audio artifact): content[0] is the (unchanged) leading text item followed
// by one resource_link whose URI is gs://{bucket}/{object}, carrying the audio MIME
// type and the "lyria output 1 of 1" description (design #483, review NB-1). The
// helper builds the gs:// URI itself, so the test is network-free.
func TestAppendLyriaResourceLinkGCS(t *testing.T) {
	text := mcp.TextContent{Type: "text", Text: "Generated audio."}
	content := appendLyriaResourceLink([]mcp.Content{text}, "my-bucket", "lyria_outputs/track.wav", "audio/wav")

	if len(content) != 2 {
		t.Fatalf("expected 2 content items (text + 1 link), got %d", len(content))
	}
	if got, ok := content[0].(mcp.TextContent); !ok || got.Text != text.Text {
		t.Fatalf("content[0] = %#v, want unchanged text %q", content[0], text.Text)
	}
	link, ok := content[1].(mcp.ResourceLink)
	if !ok {
		t.Fatalf("content[1] = %T, want mcp.ResourceLink", content[1])
	}
	if link.Type != mcp.ContentTypeLink {
		t.Errorf("content[1].Type = %q, want %q", link.Type, mcp.ContentTypeLink)
	}
	if link.URI != "gs://my-bucket/lyria_outputs/track.wav" {
		t.Errorf("content[1].URI = %q, want gs://my-bucket/lyria_outputs/track.wav", link.URI)
	}
	if link.MIMEType != "audio/wav" {
		t.Errorf("content[1].MIMEType = %q, want audio/wav", link.MIMEType)
	}
	if link.Description != "lyria output 1 of 1" {
		t.Errorf("content[1].Description = %q, want %q", link.Description, "lyria output 1 of 1")
	}
}

// TestAppendLyriaResourceLinkNoLink is the inline/local-only regression guard.
// Lyria emits a link only when BOTH a GCS bucket and an uploaded object name are
// present (GCS and inline audio are mutually exclusive); a missing bucket OR object
// name ⇒ content returned unchanged, so the inline audio path is never given a link.
func TestAppendLyriaResourceLinkNoLink(t *testing.T) {
	text := mcp.TextContent{Type: "text", Text: "Audio returned inline."}
	cases := map[string]struct {
		bucket string
		object string
	}{
		"no bucket, no object (inline)": {"", ""},
		"bucket set, object missing":    {"my-bucket", ""},
		"object set, bucket missing":    {"", "lyria_outputs/track.wav"},
	}
	for name, tc := range cases {
		t.Run(name, func(t *testing.T) {
			content := appendLyriaResourceLink([]mcp.Content{text}, tc.bucket, tc.object, "audio/wav")
			if len(content) != 1 {
				t.Fatalf("expected 1 content item (text only, no link), got %d", len(content))
			}
			if _, ok := content[0].(mcp.TextContent); !ok {
				t.Fatalf("content[0] = %T, want mcp.TextContent", content[0])
			}
		})
	}
}
