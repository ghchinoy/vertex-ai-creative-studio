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

// Package common provides shared utilities for the MCP Genmedia servers.

package common

import (
	"path"
	"strings"

	"github.com/mark3labs/mcp-go/mcp"
)

// MediaResult describes one persisted artifact for building tool-result content.
// It is the neutral input to the content builder; servers populate whichever
// fields they have (a server with API-controlled GCS has GCSURI + MimeType; a
// server using PersistMediaOutputs has all of them via PersistedMedia).
type MediaResult struct {
	// GCSURI is the "gs://bucket/obj" canonical, non-expiring identity of the
	// artifact. It is empty when the artifact was not written to GCS. Only
	// artifacts with a GCSURI produce a resource_link.
	GCSURI string
	// LocalPath is the local file path written, if any. Carried for completeness;
	// local-only artifacts do not produce a resource_link this PR.
	LocalPath string
	// SignedURL is a best-effort HTTPS V4 URL, if any. Servers keep surfacing it
	// in their text output; it is not used as the resource_link identity because
	// signed URLs expire.
	SignedURL string
	// Name is the display basename for the link. When empty it defaults to
	// path.Base of the GCS object.
	Name string
	// MimeType is the media MIME type, e.g. "image/png", "video/mp4".
	MimeType string
	// Description is the human-readable link description, e.g.
	// "nanobanana output 1 of 4" (1-based).
	Description string
}

// ResourceLinksForMedia builds one mcp.ResourceLink per artifact that has a
// gs:// URI, using the gs:// URI as the resource identity. Artifacts with no
// GCSURI produce no link (inline/local-only are handled by the caller's text
// path this PR). When Name is empty it defaults to path.Base of the GCS object.
// Returns nil if there is nothing to link.
func ResourceLinksForMedia(results []MediaResult) []mcp.Content {
	var out []mcp.Content
	for _, r := range results {
		if r.GCSURI == "" {
			continue
		}
		name := r.Name
		if name == "" {
			name = path.Base(strings.TrimPrefix(r.GCSURI, "gs://"))
		}
		out = append(out, mcp.NewResourceLink(r.GCSURI, name, r.Description, r.MimeType))
	}
	return out
}

// AppendMediaContent appends the resource links for results to an existing
// content slice (which already holds the caller's TextContent). Text building
// stays entirely in the caller — this helper only ADDS links, so existing text
// output is unchanged.
func AppendMediaContent(items []mcp.Content, results []MediaResult) []mcp.Content {
	return append(items, ResourceLinksForMedia(results)...)
}

// MediaResultFromPersisted adapts a PersistMediaOutputs result (used by
// nanobanana and RenderOmniResult) into a MediaResult. Name is left empty so
// ResourceLinksForMedia defaults it to path.Base of the GCS object.
func MediaResultFromPersisted(p PersistedMedia, mimeType, description string) MediaResult {
	return MediaResult{
		GCSURI:      p.GCSURI,
		LocalPath:   p.LocalPath,
		SignedURL:   p.SignedURL,
		MimeType:    mimeType,
		Description: description,
	}
}
