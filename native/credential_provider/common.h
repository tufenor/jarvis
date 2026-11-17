#pragma once

#include <windows.h>
#include <credentialprovider.h>

enum JARVIS_FIELD_ID
{
    JFI_TILE_IMAGE = 0,
    JFI_TITLE,
    JFI_STATUS,
    JFI_INSTRUCTION,
    JFI_NUM_FIELDS
};

struct JARVIS_FIELD_STATE_PAIR
{
    CREDENTIAL_PROVIDER_FIELD_STATE state;
    CREDENTIAL_PROVIDER_FIELD_INTERACTIVE_STATE interactive;
};

static const JARVIS_FIELD_STATE_PAIR s_rgFieldStatePairs[JFI_NUM_FIELDS] =
{
    { CPFS_DISPLAY_IN_BOTH,          CPFIS_NONE },
    { CPFS_DISPLAY_IN_BOTH,          CPFIS_NONE },
    { CPFS_DISPLAY_IN_SELECTED_TILE, CPFIS_NONE },
    { CPFS_DISPLAY_IN_SELECTED_TILE, CPFIS_NONE }
};

static const CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR s_rgFieldDescriptors[JFI_NUM_FIELDS] =
{
    { JFI_TILE_IMAGE,    CPFT_TILE_IMAGE, const_cast<PWSTR>(L"JARVIS") },
    { JFI_TITLE,         CPFT_LARGE_TEXT, const_cast<PWSTR>(L"JARVIS") },
    { JFI_STATUS,        CPFT_SMALL_TEXT, const_cast<PWSTR>(L"Status") },
    { JFI_INSTRUCTION,   CPFT_SMALL_TEXT, const_cast<PWSTR>(L"Instrução") }
};
