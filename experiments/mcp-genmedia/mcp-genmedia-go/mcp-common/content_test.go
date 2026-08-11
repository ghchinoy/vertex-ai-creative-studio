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

package common

import (
	"testing"

	"github.com/mark3labs/mcp-go/mcp"
)

// asResourceLink asserts that a content item is a resource_link and returns it.
func asResourceLink(t *testing.T, c mcp.Content) mcp.ResourceLink {
	t.Helper()
	rl, ok := c.(mcp.ResourceLink)
	if !ok {
		t.Fatalf("content is %T, want mcp.ResourceLink", c)
	}
	if rl.Type != mcp.ContentTypeLink {
		t.Errorf("Type = %q, want %q", rl.Type, mcp.ContentTypeLink)
	}
	return rl
}

func TestResourceLinksForMedia_ZeroArtifacts(t *testing.T) {
	if got := ResourceLinksForMedia(nil); got != nil {
		t.Errorf("nil input = %v, want nil", got)
	}
	if got := ResourceLinksForMedia([]MediaResult{}); got != nil {
		t.Errorf("empty input = %v, want nil", got)
	}
}

func TestResourceLinksForMedia_SingleGCSArtifact(t *testing.T) {
	results := []MediaResult{{
		GCSURI:      "gs://bucket/prefix/object.png",
		Name:        "object.png",
		MimeType:    "image/png",
		Description: "nanobanana output 1 of 1",
	}}
	got := ResourceLinksForMedia(results)
	if len(got) != 1 {
		t.Fatalf("len = %d, want 1", len(got))
	}
	rl := asResourceLink(t, got[0])
	if rl.URI != "gs://bucket/prefix/object.png" {
		t.Errorf("URI = %q, want gs://bucket/prefix/object.png", rl.URI)
	}
	if rl.Name != "object.png" {
		t.Errorf("Name = %q, want object.png", rl.Name)
	}
	if rl.MIMEType != "image/png" {
		t.Errorf("MIMEType = %q, want image/png", rl.MIMEType)
	}
	if rl.Description != "nanobanana output 1 of 1" {
		t.Errorf("Description = %q, want %q", rl.Description, "nanobanana output 1 of 1")
	}
}

func TestResourceLinksForMedia_NArtifactsInOrder(t *testing.T) {
	results := []MediaResult{
		{GCSURI: "gs://b/a.png", Name: "a.png", MimeType: "image/png", Description: "t output 1 of 3"},
		{GCSURI: "gs://b/b.png", Name: "b.png", MimeType: "image/png", Description: "t output 2 of 3"},
		{GCSURI: "gs://b/c.png", Name: "c.png", MimeType: "image/png", Description: "t output 3 of 3"},
	}
	got := ResourceLinksForMedia(results)
	if len(got) != 3 {
		t.Fatalf("len = %d, want 3", len(got))
	}
	wantURIs := []string{"gs://b/a.png", "gs://b/b.png", "gs://b/c.png"}
	for i, c := range got {
		rl := asResourceLink(t, c)
		if rl.URI != wantURIs[i] {
			t.Errorf("link[%d].URI = %q, want %q", i, rl.URI, wantURIs[i])
		}
	}
}

func TestResourceLinksForMedia_EmptyGCSURIProducesNoLink(t *testing.T) {
	results := []MediaResult{{
		LocalPath:   "/tmp/x.png",
		MimeType:    "image/png",
		Description: "local only",
	}}
	if got := ResourceLinksForMedia(results); got != nil {
		t.Errorf("empty GCSURI produced %v, want nil", got)
	}
}

func TestResourceLinksForMedia_EmptyNameDefaultsToBase(t *testing.T) {
	results := []MediaResult{{
		GCSURI:      "gs://bucket/some/prefix/object.png",
		MimeType:    "image/png",
		Description: "t output 1 of 1",
	}}
	got := ResourceLinksForMedia(results)
	if len(got) != 1 {
		t.Fatalf("len = %d, want 1", len(got))
	}
	rl := asResourceLink(t, got[0])
	if rl.Name != "object.png" {
		t.Errorf("Name = %q, want object.png (path.Base default)", rl.Name)
	}
}

func TestResourceLinksForMedia_MixedSliceOnlyGCS(t *testing.T) {
	results := []MediaResult{
		{GCSURI: "gs://b/a.png", MimeType: "image/png", Description: "t output 1 of 3"},
		{LocalPath: "/tmp/b.png", MimeType: "image/png", Description: "t output 2 of 3"}, // no GCS -> skipped
		{GCSURI: "gs://b/c.png", MimeType: "image/png", Description: "t output 3 of 3"},
	}
	got := ResourceLinksForMedia(results)
	if len(got) != 2 {
		t.Fatalf("len = %d, want 2 (only GCS artifacts)", len(got))
	}
	if rl := asResourceLink(t, got[0]); rl.URI != "gs://b/a.png" {
		t.Errorf("link[0].URI = %q, want gs://b/a.png", rl.URI)
	}
	if rl := asResourceLink(t, got[1]); rl.URI != "gs://b/c.png" {
		t.Errorf("link[1].URI = %q, want gs://b/c.png", rl.URI)
	}
}

func TestAppendMediaContent_PreservesLeadingTextThenAppends(t *testing.T) {
	text := mcp.TextContent{Type: "text", Text: "human-readable summary"}
	items := []mcp.Content{text}
	results := []MediaResult{
		{GCSURI: "gs://b/a.png", MimeType: "image/png", Description: "t output 1 of 2"},
		{GCSURI: "gs://b/b.png", MimeType: "image/png", Description: "t output 2 of 2"},
	}
	got := AppendMediaContent(items, results)
	if len(got) != 3 {
		t.Fatalf("len = %d, want 3 (text + 2 links)", len(got))
	}
	// Leading text preserved byte-for-byte.
	gotText, ok := got[0].(mcp.TextContent)
	if !ok {
		t.Fatalf("content[0] is %T, want mcp.TextContent", got[0])
	}
	if gotText.Text != "human-readable summary" {
		t.Errorf("content[0].Text = %q, want unchanged summary", gotText.Text)
	}
	// Links appended after the text, in order.
	if rl := asResourceLink(t, got[1]); rl.URI != "gs://b/a.png" {
		t.Errorf("content[1].URI = %q, want gs://b/a.png", rl.URI)
	}
	if rl := asResourceLink(t, got[2]); rl.URI != "gs://b/b.png" {
		t.Errorf("content[2].URI = %q, want gs://b/b.png", rl.URI)
	}
}

func TestAppendMediaContent_NoGCSLeavesItemsUnchanged(t *testing.T) {
	text := mcp.TextContent{Type: "text", Text: "summary"}
	items := []mcp.Content{text}
	results := []MediaResult{{LocalPath: "/tmp/x.png", MimeType: "image/png"}}
	got := AppendMediaContent(items, results)
	if len(got) != 1 {
		t.Fatalf("len = %d, want 1 (no links appended)", len(got))
	}
	if _, ok := got[0].(mcp.TextContent); !ok {
		t.Fatalf("content[0] is %T, want mcp.TextContent", got[0])
	}
}

func TestMediaResultFromPersisted_MapsFields(t *testing.T) {
	p := PersistedMedia{
		GCSURI:    "gs://bucket/obj.png",
		LocalPath: "/tmp/obj.png",
		SignedURL: "https://storage.googleapis.com/signed",
	}
	got := MediaResultFromPersisted(p, "image/png", "nanobanana output 2 of 4")
	if got.GCSURI != p.GCSURI {
		t.Errorf("GCSURI = %q, want %q", got.GCSURI, p.GCSURI)
	}
	if got.LocalPath != p.LocalPath {
		t.Errorf("LocalPath = %q, want %q", got.LocalPath, p.LocalPath)
	}
	if got.SignedURL != p.SignedURL {
		t.Errorf("SignedURL = %q, want %q", got.SignedURL, p.SignedURL)
	}
	if got.MimeType != "image/png" {
		t.Errorf("MimeType = %q, want image/png", got.MimeType)
	}
	if got.Description != "nanobanana output 2 of 4" {
		t.Errorf("Description = %q, want %q", got.Description, "nanobanana output 2 of 4")
	}
	if got.Name != "" {
		t.Errorf("Name = %q, want empty (so ResourceLinksForMedia defaults to path.Base)", got.Name)
	}
}
